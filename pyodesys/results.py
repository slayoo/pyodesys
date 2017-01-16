# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division, print_function)

import numpy as np

from .plotting import plot_result, plot_phase_plane


class Result(object):

    def __init__(self, xout, yout, params, info, odesys):
        self.xout = xout
        self.yout = yout
        self.params = params
        self.info = info
        self.odesys = odesys

    def __len__(self):
        return 3

    def __getitem__(self, key):
        if key == 0:
            return self.xout
        elif key == 1:
            return self.yout
        elif key == 2:
            return self.info
        elif key == 3:
            raise StopIteration
        else:
            raise KeyError("Invalid key: %s (for backward compatibility reasons)." % str(key))

    def _internal(self, key, override=None):
        if override is None:
            return self.info['internal_' + key]
        else:
            return override

    def stiffness(self, xyp=None, eigenvals_cb=None):
        """ Running stiffness ratio from last integration.

        Calculate sittness ratio, i.e. the ratio between the largest and
        smallest absolute eigenvalue of the jacobian matrix. The user may
        supply their own routine for calculating the eigenvalues, or they
        will be calculated from the SVD (singular value decomposition).
        Note that calculating the SVD for any but the smallest Jacobians may
        prove to be prohibitively expensive.

        Parameters
        ----------
        xyp : length 3 tuple (default: None)
            internal_xout, internal_yout, internal_params, taken
            from last integration if not specified.
        eigenvals_cb : callback (optional)
            Signature (x, y, p) (internal variables), when not provided an
            internal routine will use ``self.j_cb`` and ``scipy.linalg.svd``.

        """
        if eigenvals_cb is None:
            if self.odesys.band is not None:
                raise NotImplementedError
            eigenvals_cb = self.odesys._jac_eigenvals_svd

        if xyp is None:
            x, y, intern_p = self._internal('xout'), self._internal('yout'), self._internal('params')
        else:
            x, y, intern_p = self.pre_process(*xyp)

        singular_values = []
        for xval, yvals in zip(x, y):
            singular_values.append(eigenvals_cb(xval, yvals, intern_p))

        return (np.abs(singular_values).max(axis=-1) /
                np.abs(singular_values).min(axis=-1))


    def _plot(self, cb, internal_xout=None, internal_yout=None, internal_params=None, **kwargs):
        kwargs = kwargs.copy()
        if 'x' in kwargs or 'y' in kwargs or 'params' in kwargs:
            raise ValueError("x and y from internal_xout and internal_yout")

        if 'post_processors' not in kwargs:
            kwargs['post_processors'] = self.odesys.post_processors

        if 'names' not in kwargs:
            kwargs['names'] = getattr(self.odesys, 'names', None)
        else:
            if 'indices' not in kwargs and getattr(self.odesys, 'names', None) is not None:
                kwargs['indices'] = [self.odesys.names.index(n) for n in kwargs['names']]
                kwargs['names'] = self.odesys.names
        return cb(self._internal('xout', internal_xout),
                  self._internal('yout', internal_yout),
                  self._internal('params', internal_params), **kwargs)

    def plot(self, **kwargs):
        """ Plots the integrated dependent variables from last integration.

        Parameters
        ----------
        indices : iterable of int
        names : iterable of str
        \*\*kwargs:
            See :func:`pyodesys.plotting.plot_result`
        """
        return self._plot(plot_result, **kwargs)

    def plot_phase_plane(self, indices=None, **kwargs):
        """ Plots a phase portrait from last integration.

        Parameters
        ----------
        indices : iterable of int
        names : iterable of str
        \*\*kwargs:
            See :func:`pyodesys.plotting.plot_phase_plane`

        """
        return self._plot(plot_phase_plane, indices=indices, **kwargs)

    def plot_invariant_violations(self):
        invar = self.odesys.get_invariants_callback()
        abs_viol = invar(self._internal('xout'), self._internal('yout'), self._internal('params'))
        invar_names = self.odesys.all_invariant_names()
        return self._plot(plot_result, internal_yout=abs_viol, names=invar_names)
