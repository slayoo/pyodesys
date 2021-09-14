"""Handle common cses among groups of code."""

from collections import defaultdict
from functools import reduce
from operator import add
import numpy as np

import sympy
from sympy import numbered_symbols
from sympy.codegen.ast import Assignment, Variable, float64
from sympy.codegen.rewriting import create_expand_pow_optimization

from .core import NullTransformer
from .util import CPrinter, Backend, ccode

expand_up_to_3 = create_expand_pow_optimization(3)


def pre_process(expr):
    """Simplify, expand & factor.

    Example: expr.simplify(rational=True).expand().factor()"""
    return expr.factor()


def post_process(expr):
    """Expand low integer powers."""
    return expand_up_to_3(expr)


class GroupwiseCSE:
    """Eliminate common sub-expressions from groups of expressions."""

    def __init__(
        self,
        groups,
        *,
        common_cse_template="common_cse{0}",
        common_ignore=(),
        code_printer=None,
        subsd=None,
        transformers=None,
        type_=(lambda lhs, rhs: (float64, rhs)),
        pre_process=None,
        post_process=None,
        backend=None,
        transformer_kws=None
    ):
        """
        Parameters
        ----------
        groups : list like
        \\*\\*kwargs : see code for now.

        """
        if transformers is None:
            transformers = defaultdict(lambda: NullTransformer)
        if code_printer is None:
            code_printer = CPrinter()
        if transformer_kws is None:
            transformer_kws = defaultdict(dict)
        self._code_printer = code_printer
        self._type = type_
        self._keys, _values = zip(*groups.items())
        self._spans = np.cumsum([0] + list(map(len, _values)))
        if backend is None:
            backend = Backend()
        self.backend = backend
        _all_values = reduce(add, map(list, _values))
        _all_exprs = list(map(pre_process, _all_values) if pre_process else _all_values)
        _all_exprs = [
            e.replace(lambda s: s.is_Symbol, lambda s: sympy.Symbol(s.name, real=True))
            for e in _all_exprs
        ]
        common_ignore = [sympy.Symbol(ig.name, real=True) for ig in common_ignore]
        for e in _all_exprs:
            for fs in e.free_symbols:
                if not fs.is_real:
                    # Switching between symengine/sympy is tricky, consistently using
                    # real=True with Symbols allows us to assume real=True for SymEngine
                    # symbols (which lack support for assumptions at the time of writing).
                    raise NotImplementedError(
                        "Only use explicitly real valued symbols."
                    )
        repls, reds = self._common_cse(
            _all_exprs,
            ignore=common_ignore,
            symbols=numbered_symbols("cse_comm_locl", real=True),
        )
        if post_process:
            repls = [(s, post_process(e)) for s, e in repls]
            reds = [post_process(e) for e in reds]
        self._comm_tformr = transformers[None](
            repls, reds, ignore=common_ignore, **transformer_kws[None]
        )
        remap = self._comm_tformr.remapping_for_arrayification(
            template=common_cse_template
        )
        self._comm_tformr.apply_remapping(remap)
        _subsd = {sympy.Symbol(k.name, real=True): v for k, v in (subsd or {}).items()}
        self._comm_tformr.apply_remapping(_subsd)
        self.n_remapped = len(remap)

        assert len(self._comm_tformr.final_exprs) == len(reds)
        del reds
        self._per_g_tformrs = self._get_g_tformrs(
            self._comm_tformr,
            transformers=transformers,
            transformer_kws=transformer_kws,
            post_process=post_process,
            subsd=_subsd,
        )

    @property
    def keys(self):
        """Retrieve the keys of the groups."""
        return self._keys

    def render(self, x):
        """Generate a code string."""
        return self._code_printer.doprint(x)

    def _common_cse(self, all_exprs, **kwargs):
        repls, reds = self.backend.cse(all_exprs, **kwargs)
        cse_symbols = numbered_symbols("cse_t", real=True)  # local temporaries
        comm_subs = {}
        for lhs, rhs in repls:
            for expr in reds:
                if lhs in expr.free_symbols:
                    comm_subs[lhs] = next(cse_symbols)
                    break
        return (
            [(lhs.xreplace(comm_subs), rhs.xreplace(comm_subs)) for lhs, rhs in repls],
            [r.xreplace(comm_subs) for r in reds],
        )

    def _get_g_tformrs(
        self, comm_tformr, *, transformers, transformer_kws, post_process, subsd
    ):
        per_g = {}
        for i, k in enumerate(self._keys):
            g_repls, g_exprs = self.backend.cse(
                comm_tformr.final_exprs[slice(*self._spans[i : i + 2])],
                symbols=numbered_symbols("cse", real=True),
            )
            if post_process:
                g_repls = [(s, post_process(e)) for s, e in g_repls]
                g_exprs = [post_process(e) for e in g_exprs]
            g_tformr = transformers[k](
                g_repls, g_exprs, parent=comm_tformr, **transformer_kws[k]
            )
            g_tformr.apply_remapping(subsd)
            per_g[k] = g_tformr

        return per_g

    @staticmethod
    def _declare(stmts, *, pred, type_=float64):
        seen = set()
        result = []
        for st in stmts:
            if isinstance(st, Assignment) and st.lhs not in seen and pred(st.lhs):
                seen.add(st.lhs)
                st = Variable(st.lhs, type=type_).as_Declaration(value=st.rhs)
            result.append(st)
        return result

    def common_statements(self, declare=False, type_=None):
        """Initialize the common sub-expressions among the groups."""
        if declare:
            return self._comm_tformr.statements_with_declarations(
                pred=declare, type_=type_ or self._type
            )
        else:
            return self._comm_tformr.statements

    def statements(self, gk, declare=False, type_=None):
        """Initialize the group specific sub-expressions."""
        if declare:
            return self._per_g_tformrs[gk].statements_with_declarations(
                pred=declare, type_=type_ or self._type
            )
        else:
            return self._per_g_tformrs[gk].statements

    def exprs(self, gk):
        """Retrieve the resulting expressions of the group named ``key``."""
        return self._per_g_tformrs[gk].final_exprs