import Mathlib.Tactic.NoncommRing

/- Equality of a left and a right quasi-inverse in §1.2.
   R may lack an identity. hb and hc are exactly the two displayed
   quasi-inverse equations, with the book's plus-sign convention. -/
namespace Herstein.QuasiInverse

theorem left_right_equal {R : Type*} [NonUnitalRing R] (a b c : R)
    (hb : a + b + b * a = 0) (hc : a + c + a * c = 0) : b = c := by
  have first : b * a + b * c + (b * a) * c = 0 := by
    calc
      _ = b * (a + c + a * c) := by noncomm_ring
      _ = 0 := by rw [hc, mul_zero]
  have second : a * c + b * c + (b * a) * c = 0 := by
    calc
      _ = (a + b + b * a) * c := by noncomm_ring
      _ = 0 := by rw [hb, zero_mul]
  have crossed : b * a = a * c := by
    have h : b * a + (b * c + (b * a) * c) =
        a * c + (b * c + (b * a) * c) := by
      calc
        b * a + (b * c + (b * a) * c) = 0 := by
          simpa only [add_assoc] using first
        _ = _ := by simpa only [add_assoc] using second.symm
    exact add_right_cancel h
  have h : a + b + a * c = a + c + a * c := by
    calc
      a + b + a * c = a + b + b * a := by rw [crossed]
      _ = 0 := hb
      _ = _ := hc.symm
  exact add_left_cancel (add_right_cancel h)

#print axioms left_right_equal
end Herstein.QuasiInverse
