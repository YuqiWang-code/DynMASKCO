from fractions import Fraction as F
from itertools import combinations

def gauss(M, rhs):
    n = len(M); m = len(M[0])
    A = [row[:] + [rhs[i]] for i, row in enumerate(M)]
    r = 0
    for c in range(m):
        p = None
        for i in range(r, n):
            if A[i][c] != 0:
                p = i; break
        if p is None:
            continue
        A[r], A[p] = A[p], A[r]
        pv = A[r][c]
        A[r] = [v / pv for v in A[r]]
        for i in range(n):
            if i != r and A[i][c] != 0:
                f = A[i][c]
                A[i] = [A[i][j] - f * A[r][j] for j in range(m + 1)]
        r += 1
        if r == n:
            break
    for i in range(r, n):
        if all(A[i][j] == 0 for j in range(m)) and A[i][m] != 0:
            return None
    x = [F(0)] * m
    for i in range(min(r, n)):
        lead = None
        for j in range(m):
            if A[i][j] != 0:
                lead = j; break
        if lead is not None:
            x[lead] = A[i][m]
    return x

def game_value(A):
    rows = len(A); cols = len(A[0])
    best = None
    for s in range(1, min(rows, cols) + 1):
        for S in combinations(range(rows), s):
            for K in combinations(range(cols), s):
                M = [[F(A[j][k]) for j in S] + [F(-1)] for k in K]
                rhs = [F(0)] * s
                M.append([F(1)] * s + [F(0)]); rhs.append(F(1))
                sol = gauss(M, rhs)
                if sol is None:
                    continue
                xs = sol[:s]; t = sol[s]
                if any(v < 0 for v in xs) or sum(xs) != 1:
                    continue
                if all(sum(xs[i] * F(A[S[i]][k]) for i in range(s)) >= t for k in range(cols)):
                    full = [F(0)] * rows
                    for i, j in enumerate(S):
                        full[j] = xs[i]
                    if best is None or t > best[0]:
                        best = (t, full)
    return best

def transpose(A):
    return [[A[j][k] for j in range(len(A))] for k in range(len(A[0]))]

def show(name, A):
    v, x = game_value(A)
    vt, q = game_value(transpose(A))
    print('%s' % name)
    print('  upper(min_x max_k) = %s' % v)
    print('  x*                 = %s' % ([str(t) for t in x],))
    print('  yao(max_q min_j)   = %s' % vt)
    print('  q*                 = %s' % ([str(t) for t in q],))
    print('  tight(upper==lower)= %s' % (v == vt))
    return v, x, q

show('S1 [[0,1],[1,0]]', [[0, 1], [1, 0]])
show('S2 [[0,1],[1,1/3]]', [[F(0), F(1)], [F(1), F(1, 3)]])
# ??????=???(accept_L=0, accept_L=1)??=??(A=? L ???, C=??)
cert = [[F(0), F(1)], [F(1), F(1, 3)]]
v, x, q = show('CERT 2x2 from Q1 ratios', cert)
print()
print('[CERT] deterministic sup = max_j min_k = %s' % max(min(r) for r in cert))
print('[CERT] randomised LP value = %s (expected 3/5)' % v)
print('[CERT] value == 3/5 : %s' % (v == F(3, 5)))
print('[CERT] yao distribution q = %s' % ([str(t) for t in q],))
