"""Exact small examples for the character and Hurwitz formulas of Chapter 5.

C3 tests the position of conjugation in the column orthogonality identity
and of the dual in the tensor-product criterion. The two-dimensional
matrix example distinguishes anticommutation from orthogonal relations;
it does not classify representations or prove the Hurwitz bound.
Passages: th:character-column-orthogonality, lem:tensor-unit-contragredient,
th:hurwitz-matrix-bound, th:frobenius-kernel. The symmetric group of order
six distinguishes kernels from scalar preimages in the Frobenius proof.
"""
from itertools import permutations
from sage.all import CyclotomicField, QuadraticField, identity_matrix, matrix

count = 0


def check(claim):
    global count
    assert claim
    count += 1


C = CyclotomicField(3)
z = C.gen()
characters = [C(1), z, z**2]
check(sum(c*c for c in characters) == 0)
check(sum(c*c.conjugate() for c in characters) == 3)
at_inverse = [c.conjugate() for c in characters]
check(sum(a*b for a, b in zip(characters, at_inverse)) == 3)
check(sum(a*b.conjugate() for a, b in zip(characters, at_inverse)) == 0)
check(z != z.conjugate())
check(z*z.conjugate() == 1)

# In S3 with a subgroup of order two, the Frobenius complement is A3.
# The nonunit subgroup character leads to the sign character of S3.
G = list(permutations(range(3)))
sign = lambda g: (-1)**sum(g[a] > g[b] for a in range(3) for b in range(a+1, 3))
kernel = [g for g in G if sign(g) == 1]
scalar_preimage = [g for g in G if abs(sign(g)) == 1]
check(len(kernel) == 3)
check(len(scalar_preimage) == 6)

F = QuadraticField(-1, 'i')
i = F.gen()
I = identity_matrix(F, 2)
J = matrix(F, [[0, 1], [-1, 0]])
K = matrix(F, [[i, 0], [0, -i]])
check(J*J == -I)
check(K*K == -I)
check(J*K == -K*J)
check(J.transpose()*J == I)
check(K.transpose()*K == -I)
# Every symmetric 2x2 form has the following three basis matrices.
forms = [matrix(F, [[1, 0], [0, 0]]),
         matrix(F, [[0, 1], [1, 0]]),
         matrix(F, [[0, 0], [0, 1]])]
system = matrix(F, [(J.transpose()*S+S*J).list()
                    + (K.transpose()*S+S*K).list() for S in forms]).transpose()
check(system.right_kernel().dimension() == 0)
# All skew-symmetric 2x2 matrices are scalar multiples of J. Their
# anticommutator is -2abI; invertible multiples cannot anticommute.
check(J*J+J*J == -2*I)
print(f'ok representations: {count} checks')
