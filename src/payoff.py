"""
Various payoff functions.
"""

import contextlib
import numpy as np

__all__ = [
        "Payoff",
        # Simple Payoffs
        "CallA", "CallE", "CallVR", "Forward", "PutA", "PutE", "PutV",
        # Compound Payoffs
        "Stack", "Time", "UpAndOut",
        # Stock Independent Payoffs
        "Annuity", "AnnuityI",
        # Behaviour Mutators
        "VariableStrike",
    ]


class Payoff(object):
    """
    The payoff description for a derivative, handling terminal, transient
    and default payoffs.
    """

    def __init__(self, T):
        self.T = T

    def __contains__(self, t):
        return 0 <= t <= T

    def default(self, t, S):
        """Payoff in the event of default at time t"""
        assert(t != self.T)
        return np.zeros(S.shape)

    def terminal(self, S):
        """Payoff at terminal time."""
        return np.zeros(S.shape)

    def transient(self, t, V, S):
        """Payoff during transient (non-terminal) time."""
        assert(t != self.T)
        return V

    def coupon(self, t):
        """Payoff of coupon."""
        return 0


###
### SIMPLE PAYOFFS
###

class Forward(Payoff):
    """
    An Forward payoff, with total default and strike K.
    """

    def __init__(self, T, K):
        super(Forward, self).__init__(T)
        self.K = np.double(K)

    def terminal(self, S):
        """Terminal payoff of ``S - K''."""
        return S - self.K


###
### OPTIONAL PAYOFFS
###


class CallE(Payoff):
    """
    An European Call payoff, with total default and strike K.
    """

    def __init__(self, T, K):
        super(CallE, self).__init__(T)
        self.K = np.double(K)

    def terminal(self, S):
        """Terminal payoff of ``max(S - K, 0)''."""
        return np.maximum(S - self.K, 0)


class CallA(CallE):
    """
    An American Call payoff, with total default and strike K.
    """

    def __init__(self, T, K):
        super(CallA, self).__init__(T, K)

    def default(self, t, S):
        """Residual value of default."""
        assert(t != self.T)
        return np.maximum(S - self.K, 0)

    def transient(self, t, V, S):
        """Transient payoff of ``max(S - K, V)''."""
        assert(t != self.T)
        return np.maximum(V, S - self.K)


class PutE(Payoff):
    """
    An European Put payoff, with total default and strike K.
    """

    def __init__(self, T, K):
        super(PutE, self).__init__(T)
        self.K = np.double(K)

    def terminal(self, S):
        """Terminal payoff of ``max(K - S, 0)''."""
        return np.maximum(self.K - S, 0)


class PutA(PutE):
    """
    An American Put payoff, with total default and strike K.
    """

    def __init__(self, T, K):
        super(PutA, self).__init__(T, K)

    def default(self, t, S):
        """Residual value of default."""
        assert(t != self.T)
        return np.maximum(self.K - S, 0)

    def transient(self, t, V, S):
        """Transient payoff of ``max(K - S, V)''."""
        assert(t != self.T)
        return np.maximum(V, self.K - S)


###
### OPTIONAL PAYOFFS BASED ON PORTFOLIO VALUE
###


class PutV(Payoff):
    """
    An American Put payoff, with total default and strike K, on the value of
    the portfolio,
    """

    def __init__(self, T, K):
        super(PutV, self).__init__(T)
        self.K = np.double(K)

    def transient(self, t, V, _S):
        """Transient payoff of ``V + max(K - V, 0)''."""
        assert(t != self.T)
        return np.maximum(V, self.K)


class CallVR(Payoff):
    """
    A reverse American Call payoff, with total default and strike K, on the
    value of the portfolio.
    """

    def __init__(self, T, K):
        super(CallVR, self).__init__(T)
        self.K = np.double(K)

    def transient(self, t, V, _S):
        """Transient payoff of ``V - max(V - K, 0)''."""
        assert(t != self.T)
        return np.minimum(V, self.K)


###
### COMPOUND PAYOFFS
###


class Stack(Payoff):
    """
    Stacked derivatives
    """

    def __init__(self, stack):
        super(Stack, self).__init__(stack[0].T)
        self.stack = tuple(stack)

    def default(self, t, S):
        """Maximum default value of stacked payoffs."""
        assert(t != self.T)
        V = self.stack[0].default(t, S)
        for payoff in self.stack[1:]:
            V = np.maximum(V, payoff.default(t, S))
        return V

    def transient(self, t, V, S):
        """Transient payoff of stacked payoffs."""
        assert(t != self.T)
        for payoff in self.stack:
            V = payoff.transient(t, V, S)
        return V

    def terminal(self, S):
        """Maximum transient vale of stacked payoffs."""
        V = self.stack[0].terminal(S)
        for payoff in self.stack[1:]:
            V = np.maximum(V, payoff.terminal(S))
        return np.double(V)

    def coupon(self, t):
        """Coupon payoff of stacked payoffs."""
        V = 0
        for payoff in self.stack:
            V += payoff.coupon(t)
        return V


class Time(Payoff):
    """
    Derivative with time restrictions
    """

    def __init__(self, payoff, times):
        super(Time, self).__init__(payoff.T)
        self.payoff = payoff
        self._time_discrete = set()
        self._time_continuous = []
        self.times = times

    def __contains__(self, t):
        """Check if the current time is a valid time for the payoff."""
        if t in self._time_discrete:
            return True
        for l, u in self._time_continuous:
            if l <= t <= u:
                return True
        else:
            return False

    @property
    def times(self):
        return list(self._time_discrete) + self._time_continuous

    @times.setter
    def times(self, times):
        self._time_discrete = set()
        self._time_continuous = []
        for time in times:
            try:
                l = max(np.double(time[0]), 0)
                u = min(np.double(time[1]), self.T)
                self._time_continuous.append((l, u))
            except (TypeError, IndexError):
                if 0 <= time <= self.T:
                    self._time_discrete.add(np.double(time))

    def default(self, t, S):
        """Default value of payoff, zero is out of time."""
        assert(t != self.T)
        if t in self:
            return self.payoff.default(t, S)
        else:
            return np.zeros(S.shape)

    def transient(self, t, V, S):
        """Transient value of payoff."""
        assert(t != self.T)
        if t in self:
            return self.payoff.transient(t, V, S)
        else:
            return V

    def terminal(self, S):
        """Terminal payoff, zero is out of time."""
        if self.T in self:
            return self.payoff.terminal(S)
        else:
            return 0

    def coupon(self, t):
        """Coupon payoff, zero is out of time."""
        if t in self:
            return self.payoff.coupon(t)
        else:
            return 0


class UpAndOut(Payoff):
    """
    A Up-and-Out derivative.
    """

    def __init__(self, payoff, L):
        super(UpAndOut, self).__init__(payoff.T)
        self.payoff = payoff
        self.L = np.double(L)

    def default(self, t, S):
        """Default value of payoff."""
        assert(t != self.T)
        V = np.zeros(S.shape)
        idx = S < self.L
        V[idx] = self.payoff.default(t, S[idx])
        return V

    def transient(self, t, V, S):
        """Transient payoff, 0 if above threshold, otherwise payoff."""
        Vp = np.zeros(S.shape)
        idx = S < self.L
        Vp[idx] = self.payoff.transient(t, V[idx], S[idx])
        return Vp

    def terminal(self, S):
        """Terminal payoff, 0 if above threshold, otherwise payoff."""
        V = np.zeros(S.shape)
        idx = S < self.L
        V[idx] = self.payoff.terminal(S[idx])
        return V

    def coupon(self, t):
        """Coupon payoff."""
        if t in self:
            return self.payoff.coupon(t)
        else:
            return 0


###
### STOCK INDEPENDENT PAYOFFS
###


class Annuity(Payoff):
    """
    Payment process that pays a coupon at specified times and nominal at end
    """

    def __init__(self, T, times=(), C=0, N=0, R=0):
        super(Annuity, self).__init__(T)
        self.times = times
        self.C = np.double(C)
        self.N = np.double(N)
        self.R = np.double(R)

    def __contains__(self, t):
        return t in self.times

    def default(self, t, S):
        """Residual value on default"""
        assert(t != self.T)
        return np.ones(S.shape) * self.N * self.R

    def terminal(self, S):
        """Nominal value of bond."""
        return np.ones(S.shape) * self.N

    def coupon(self, t):
        """Coupon payment."""
        if t in self:
            return self.C
        else:
            return 0.0


class AnnuityI(Payoff):
    """
    Payment process that pays a coupon at specified times and nominal at end.

    The coupon payments are intrinsic (i.e. a Stack with AnnuityI may not have
    coupons payed on due time if other payoffs overwrite coupon) and not
    guaranteed to impact the portfolio value.
    """

    def __init__(self, T, times=(), C=0, N=0, R=0):
        super(AnnuityI, self).__init__(T)
        self.times = times
        self.C = np.double(C)
        self.N = np.double(N)
        self.R = np.double(R)

    def default(self, t, S):
        """Residual value on default"""
        assert(t != self.T)
        return np.ones(S.shape) * self.N * self.R

    def transient(self, t, V, S):
        """Coupon payment added to payoff value."""
        assert(t != self.T)
        if t in self.times:
            return V + self.C
        return V

    def terminal(self, S):
        """Nominal value of bond."""
        V = np.ones(S.shape) * self.N
        if self.T in self.times:
            V += self.C
        return V


###
### BEHAVIOUR MUTATORS
###


class VariableStrike(object):
    """
    Allow easy implementation of variable strikes.
    """

    @contextlib.contextmanager
    def _strike(self, K):
        K_origin = self.K
        try:
            self.K = K
            yield
        finally:
            self.K = K_origin

    def strike(self, t):
        """Calculate the time dependent strike."""

    def transient(self, t, V, S):
        """Transient payoff"""
        K_origin = self.K
        try:
            self.K = self.strike(t)
            return super(VariableStrike, self).transient(t, V, S)
        finally:
            self.K = K_origin
