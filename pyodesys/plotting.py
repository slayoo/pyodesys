# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)


import numpy as np


def plot_result(x, y, params=(), indices=None, plot=None, plot_kwargs_cb=None, ax=None,
                ls=('-', '--', ':', '-.'),
                c=('k', 'r', 'g', 'b', 'c', 'm', 'y'),
                m=('o', 'v', '8', 's', 'p', 'x', '+', 'd', 's'),
                m_lim=-1, lines=None, interpolate=None, interp_from_deriv=None,
                names=None, latex_names=None, post_processors=(), xlabel=None, ylabel=None,
                xscale=None, yscale=None):
    """
    Plot the depepndent variables vs. the independent variable

    Parameters
    ----------
    x : array_like
        Values of the independent variable.
    y : array_like
        Values of the independent variable. This must hold
        ``y.shape[0] == len(x)``, plot_results will draw
        ``y.shape[1]`` lines. If ``interpolate != None``
        y is expected two be three dimensional, otherwise two dimensional.
    params : array_like
        Parameters used.
    indices : iterable of integers
        What indices to plot (default: None => all).
    plot : callback (default: None)
        If None, use ``matplotlib.pyplot.plot``.
    plot_kwargs_cb : callback(int) -> dict
        Keyword arguments for plot for each index (0:len(y)-1).
    ax : Axes
    ls : iterable
        Linestyles to cycle through (only used if plot and plot_kwargs_cb
        are both None).
    c : iterable
        Colors to cycle through (only used if plot and plot_kwargs_cb
        are both None).
    m : iterable
        Markers to cycle through (only used if plot and plot_kwargs_cb
        are both None and m_lim > 0).
    m_lim : int (default: -1)
        Upper limit (exclusive, number of points) for using markers instead of
        lines.
    lines : None
        default: draw between markers unless we are interpolating as well.
    interpolate : bool or int (default: None)
        Density-multiplier for grid of independent variable when interpolating
        if True => 20. negative integer signifies log-spaced grid.
    interp_from_deriv : callback (default: None)
        When ``None``: ``scipy.interpolate.BPoly.from_derivatives``
    post_processors : iterable of callback (default: tuple())

    """
    import matplotlib.pyplot as plt

    if plot is None:
        if ax is None:
            from matplotlib.pyplot import plot
        else:
            plot = ax.plot
    if plot_kwargs_cb is None:
        def plot_kwargs_cb(idx, lines=False, markers=False, labels=None):
            kwargs = {'c': c[idx % len(c)]}

            if lines:
                kwargs['ls'] = ls[idx % len(ls)]
                if isinstance(lines, float):
                    kwargs['alpha'] = lines
            else:
                kwargs['ls'] = 'None'

            if markers:
                kwargs['marker'] = m[idx % len(m)]

            if labels:
                kwargs['label'] = labels[idx]
            return kwargs
    else:
        plot_kwargs_cb = plot_kwargs_cb or (lambda idx: {})

    def post_process(x, y, p):
        for post_processor in post_processors:
            x, y, p = post_processor(x, y, p)
        return x, y, p

    if interpolate is None:
        interpolate = y.ndim == 3 and y.shape[1] > 1

    x_post, y_post, params_post = post_process(x, y[:, 0, :] if interpolate and
                                               y.ndim == 3 else y, params)
    if indices is None:
        indices = range(y_post.shape[-1])  # e.g. PartiallySolvedSys
    if lines is None:
        lines = interpolate in (None, False)
    markers = len(x) < m_lim
    for idx in indices:
        plot(x_post, y_post[:, idx], **plot_kwargs_cb(
            idx, lines=lines, labels=latex_names or names))
        if markers:
            plot(x_post, y_post[:, idx], **plot_kwargs_cb(
                idx, lines=False, markers=markers, labels=latex_names or names))

    if xlabel is None:
        try:
            plt.xlabel(x_post.dimensionality.latex)
        except AttributeError:
            pass
    else:
        plt.xlabel(xlabel)

    if ylabel is None:
        try:
            plt.ylabel(y_post.dimensionality.latex)
        except AttributeError:
            pass
    else:
        plt.ylabel(ylabel)

    if interpolate:
        if interpolate is True:
            interpolate = 20

        if isinstance(interpolate, int):
            if interpolate > 0:
                x_plot = np.concatenate(
                    [np.linspace(a, b, interpolate)
                     for a, b in zip(x[:-1], x[1:])])
            elif interpolate < 0:
                x_plot = np.concatenate([
                    np.logspace(np.log10(a), np.log10(b),
                                -interpolate) for a, b
                    in zip(x[:-1], x[1:])])
        else:
            x_plot = interpolate

        if interp_from_deriv is None:
            import scipy.interpolate
            interp_from_deriv = scipy.interpolate.BPoly.from_derivatives

        y2 = np.empty((x_plot.size, y.shape[-1]))
        for idx in range(y.shape[-1]):
            interp_cb = interp_from_deriv(x, y[..., idx])
            y2[:, idx] = interp_cb(x_plot)

        x_post2, y_post2, params2 = post_process(x_plot, y2, params)
        for idx in indices:
            plot(x_post2, y_post2[:, idx], **plot_kwargs_cb(
                idx, lines=True, markers=False))
        return x_post2, y_post2

    if xscale is not None:
        (ax or plt.gca()).set_xscale(xscale)
    if yscale is not None:
        (ax or plt.gca()).set_yscale(yscale)
    return x_post, y_post


def plot_phase_plane(x, y, params=(), indices=None, post_processors=(),
                     plot=None, names=None, **kwargs):
    """ Plot the phase portrait of two dependent variables

    Parameters
    ----------
    x: array_like
        Values of the independent variable
    y: array_like
        Values of the dependent variables
    params: array_like
        parameters
    indices: pair of integers (default: None)
        what dependent variable to plot for (None => (0, 1))
    post_processors: iterable of callbles
        see :class:ODESystem
    plot: callable (default: None)
        Uses matplotlib.pyplot.plot if None
    names: iterable of strings
        labels for x and y axis
    \*\*kwargs:
        keyword arguemtns passed to ``plot()``

    """
    if indices is None:
        indices = (0, 1)
    if len(indices) != 2:
        raise ValueError('Only two phase variables supported at the moment')

    if plot is None:
        import matplotlib.pyplot as plt
        plot = plt.plot
        if names is not None:
            plt.xlabel(names[indices[0]])
            plt.ylabel(names[indices[1]])

    for post_processor in post_processors:
        x, y, params = post_processor(x, y, params)

    plot(y[:, indices[0]], y[:, indices[1]], **kwargs)


def right_hand_ylabels(ax, labels):
    ax2 = ax.twinx()
    ylim = ax.get_ylim()
    yspan = ylim[1]-ylim[0]
    ax2.set_ylim(ylim)
    yticks = [ylim[0] + (idx + 0.5)*yspan/len(labels) for idx in range(len(labels))]
    ax2.tick_params(length=0)
    ax2.set_yticks(yticks)
    ax2.set_yticklabels(labels)


def info_vlines(ax, xout, info, vline_keys=(
        'steps', 'rhs_xvals', 'jac_xvals', 'fe_underflow',
        'fe_overflow', 'fe_invalid', 'fe_divbyzero'), vline_colors=('maroon', 'purple'),
                post_proc=None, alpha=None, fpes=None):
    import matplotlib.transforms as tf
    trans = tf.blended_transform_factory(ax.transData, ax.transAxes)
    nvk = len(vline_keys)
    for idx, key in enumerate(vline_keys):
        if key == 'steps':
            vlines = xout
        elif key.startswith('fe_'):
            if fpes is None:
                raise ValueError("Need fpes when vline_keys contain fe_*")
            vlines = xout[info['fpes'] & fpes[key.upper()] > 0]
        else:
            vlines = post_proc(info[key]) if post_proc is not None else info[key]
        if alpha is None:
            if len(vlines) < 100:
                every = 1
                alpha = 0.40
            elif len(vlines) < 300:
                every = 2
                alpha = 0.35
            elif len(vlines) < 900:
                every = 4
                alpha = 0.30
            elif len(vlines) < 2700:
                every = 8
                alpha = 0.25
            elif len(vlines) < 8100:
                every = 16
                alpha = 0.20
            elif len(vlines) < 24300:
                every = 32
                alpha = 0.15
            elif len(vlines) < 72900:
                every = 64
                alpha = 0.10
        ax.vlines(vlines[::every], idx/nvk + 0.002, (idx+1)/nvk - 0.002, colors=vline_colors[idx % len(vline_colors)],
                  alpha=alpha, transform=trans)
    right_hand_ylabels(ax, [k[3] if k.startswith('fe_') else k[0] for k in vline_keys])
