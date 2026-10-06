"""Exact matrix examples of §1.1.

The constants are the displayed matrices, read in their original order.
Checks cover the complex centralizer, the quaternion generators and their
entire linear centralizer, and the symbolic conjugate/norm identity.
They establish these explicit identities; the real positivity of the norm
and the general Schur theorem are separate arguments in the text.
Passage: display:quaternion-centralizer.
"""
from sage.all import QQ, PolynomialRing, identity_matrix, matrix

count = 0


def check(claim):
    global count
    assert claim
    count += 1


real2 = matrix(QQ, [[0, -1], [1, 0]])
P = PolynomialRing(QQ, names=('alpha', 'beta', 'gamma', 'delta'))
alpha, beta, gamma, delta = P.gens()
complex_matrix = matrix(P, [[alpha, -beta], [beta, alpha]])
check(complex_matrix * real2 == real2 * complex_matrix)
check(complex_matrix.det() == alpha**2 + beta**2)

a = matrix(QQ, [[0, -1, 0, 0], [1, 0, 0, 0],
                [0, 0, 0, -1], [0, 0, 1, 0]])
b = matrix(QQ, [[0, 0, -1, 0], [0, 0, 0, 1],
                [1, 0, 0, 0], [0, -1, 0, 0]])
I = identity_matrix(QQ, 4)
check(a*a == -I)
check(b*b == -I)
check(a*b == -b*a)
q = matrix(P, [[alpha, -beta, -gamma, -delta],
               [beta, alpha, delta, -gamma],
               [gamma, -delta, alpha, beta],
               [delta, gamma, -beta, alpha]])
check(q*a == a*q)
check(q*b == b*q)
conjugate = q.subs({beta: -beta, gamma: -gamma, delta: -delta})
norm = alpha**2 + beta**2 + gamma**2 + delta**2
check(q*conjugate == norm*I)
check(conjugate*q == norm*I)
check(q.det() == norm**2)

# Solve all 32 commuting equations as one exact rational linear system.
units = []
for i in range(4):
    for j in range(4):
        u = matrix(QQ, 4)
        u[i, j] = 1
        units.append(u)
columns = [(u*a-a*u).list() + (u*b-b*u).list() for u in units]
system = matrix(QQ, columns).transpose()
kernel = system.right_kernel()
check(kernel.dimension() == 4)
basis = [q.subs({alpha: int(k == 0), beta: int(k == 1),
                gamma: int(k == 2), delta: int(k == 3)})
         for k in range(4)]
displayed = matrix(QQ, [u.list() for u in basis]).row_space()
check(displayed == kernel)
print(f'ok modules: {count} checks')
