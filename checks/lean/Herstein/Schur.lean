import Mathlib.Algebra.Group.Subgroup.Ker

/- The kernel/image step of Theorem 1.1.1.
   M is the additive group of the book's right module. `act m r` is mr.
   The action fixes zero; irreducibility says every action-stable additive
   subgroup is zero or all of M. No identity element of R is assumed.
   Additivity and compatibility express membership in the commuting ring.
   This file does not construct the module or its commuting-ring operations. -/
namespace Herstein.Schur

variable {R M : Type*} [AddGroup M]

def Stable (act : M → R → M) (S : AddSubgroup M) : Prop :=
  ∀ m ∈ S, ∀ r, act m r ∈ S

theorem nonzero_bijective
    (act : M → R → M) (zero_act : ∀ r, act 0 r = 0)
    (irreducible : ∀ S : AddSubgroup M, Stable act S → S = ⊥ ∨ S = ⊤)
    (f : M →+ M) (commutes : ∀ m r, f (act m r) = act (f m) r)
    (nonzero : f ≠ 0) : Function.Bijective f := by
  have range_stable : Stable act f.range := by
    intro m hm r
    rcases AddMonoidHom.mem_range.mp hm with ⟨x, rfl⟩
    exact AddMonoidHom.mem_range.mpr ⟨act x r, commutes x r⟩
  have ker_stable : Stable act f.ker := by
    intro m hm r
    apply AddMonoidHom.mem_ker.mpr
    rw [commutes, AddMonoidHom.mem_ker.mp hm, zero_act]
  have image_all : f.range = ⊤ := by
    rcases irreducible f.range range_stable with hz | ht
    · exfalso
      apply nonzero
      ext m
      have hm : f m ∈ f.range := AddMonoidHom.mem_range.mpr ⟨m, rfl⟩
      rw [hz] at hm
      exact AddSubgroup.mem_bot.mp hm
    · exact ht
  have kernel_zero : f.ker = ⊥ := by
    rcases irreducible f.ker ker_stable with hz | ht
    · exact hz
    · exact False.elim (nonzero (AddMonoidHom.ker_eq_top_iff.mp ht))
  exact ⟨(AddMonoidHom.ker_eq_bot_iff f).mp kernel_zero,
    AddMonoidHom.range_eq_top.mp image_all⟩

omit [AddGroup M] in
theorem inverse_commutes
    (act : M → R → M) (f g : M → M)
    (injective : Function.Injective f)
    (right_inverse : Function.RightInverse g f)
    (commutes : ∀ m r, f (act m r) = act (f m) r) :
    ∀ m r, g (act m r) = act (g m) r := by
  intro m r
  apply injective
  rw [right_inverse, commutes, right_inverse]

#print axioms nonzero_bijective
#print axioms inverse_commutes
end Herstein.Schur
