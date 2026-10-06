// Numbered statements, proofs, examples, exercises and hints. Types and styles
// are set here, the counters in numbering.typ; chapter files only name the
// statement and give its label, a stable semantic name: `#theorem[…]
// <th:classical-real-forms>`, `#problem[…]
// <pr:simple-algebraic-group-criterion>`, `#exercise[…]
// <exc:codimension-one-normal-complement>`, `#eg
// <exm:determinant-homomorphism>`. No number is written in a chapter file:
// every number is counted (numbering.typ lists the schemes and the book's
// exceptions).
//
// As in the book: "Problem 2." bold with an upright body; theorems, lemmas,
// propositions and corollaries bold with an italic body; "Proof." italic.
#import "main-defs.typ": reference-rules
#import "numbering.typ": (
  equation-scope, family-counter, formula-skips, formula-tags, numbered-record,
  object-number, place-key, proof-equations, record, record-number,
  section-examples,
)

// The labels of the references in `it`. A hint names its problems and a
// restatement its theorem by references, `[@pr:open-map]`, not by labels
// passed as arguments, so that the editor goes to them.
#let references-in(it) = {
  if it.func() == ref { (it.target,) } else if it.has("children") {
    it.children.map(references-in).flatten()
  } else if it.has("body") { references-in(it.body) } else { () }
}

// Head of a numbered object: steps the family's counter, leaves the record
// and shows the object's own number with `format`.
#let counted(family, format) = {
  family-counter(family).step()
  if family == "exm" { section-examples.step() }
  context {
    record(family)
    format(object-number(family, here()).last())
  }
}

// Fit a display to the available column without editing its mathematical
// content. Moderate overflow shrinks; long unnumbered calculations use the
// native paragraph layout of inline math, retaining display-style operators.
#let fit-display(it) = context layout(size => {
  let natural = measure(math.equation(math.display(it.body))).width
  let reserved = if it.numbering == none { 0pt } else { text.size * 3 }
  let available = size.width - reserved
  let factor = if natural <= available { 1 } else { available / natural }
  if factor < 0.8 and it.numbering == none {
    block(width: 100%, breakable: false, {
      set align(center)
      set text(top-edge: "bounds", bottom-edge: "bounds")
      set par(justify: false, first-line-indent: 0pt, leading: 0.52em)
      math.equation(math.display(it.body))
    })
  } else { text(size: text.size * factor, it) }
})

// Number of a displayed formula with a label, `$ … $
// <eq:homomorphism-path-equation>`; the show rule of book-style.typ calls this
// for every labelled display. A display listed in `formula-tags`
// (numbering.typ) is tagged with a letter, "(F)", and not counted.
#let numbered-display(it) = {
  let name = str(it.label)
  let tag = formula-tags.at(name, default: none)
  context {
    if tag == none {
      let skip = formula-skips.at(name, default: 0)
      let active = if equation-scope.get() == none {
        family-counter("eq")
      } else { proof-equations }
      active.update(n => n + 1 + skip)
    }
    context {
      record("eq", tag: tag)
      let shown = object-number("eq", here(), tag: tag).last()
      let shown = if tag != none { emph(shown) } else { shown }
      let number-size = text.size
      fit-display(math.equation(
        block: true,
        // Upright also inside the italic text of a theorem.
        numbering: _ => text(
          font: "Libertinus Serif",
          style: "normal",
          size: number-size,
        )[(#shown)],
        number-align: end + horizon,
        it.body,
      ))
    }
  }
}

// Rebuilding a statement's first or last paragraph (to take a head or an
// ending) joins its pieces as `+` and `join` do, flattening nested sequences
// one level, but keeps a labelled sequence whole (`#eg
// <exm:additive-group-of-field>`, a problem closing a proof): `+` would merge
// it into its neighbours and lose its label. A rebuilt labelled object gets its
// label back.
#let sequence = [].func()
#let join-pieces(pieces) = sequence(
  pieces
    .map(it => if it.func() == sequence and not it.has("label") {
      it.children
    } else { (it,) })
    .flatten(),
)
#let keep-label(original, rebuilt) = {
  if original.has("label") [#rebuilt#original.label] else { rebuilt }
}

// Put `head` at the start of the first paragraph of `body`.
#let prepend-heading(body, head) = {
  if body.func() == block {
    let fields = body.fields()
    let inner = fields.remove("body")
    block(prepend-heading(inner, head), ..fields)
  } else if body.func() == sequence and body.children.len() > 0 {
    let children = body.children
    let first = children.position(it => (
      it.func()
        not in (
          [ ].func(),
          parbreak,
        )
    ))
    if first == none { join-pieces((head, body)) } else {
      keep-label(body, join-pieces((
        ..children.slice(0, first),
        prepend-heading(children.at(first), head),
        ..children.slice(first + 1),
      )))
    }
  } else { head + body }
}

// Put `ending` after the last word or formula of `body`.
#let append-ending(body, ending) = {
  if body.func() == math.equation and body.block {
    // A display does not span the line by itself; widen it so that the mark
    // stands at the right margin on the display's last line.
    block(width: 100%, {
      place(bottom + right, ending)
      body
    })
  } else if body.func() in (block, box) {
    let fields = body.fields()
    let inner = fields.remove("body")
    body.func()(append-ending(inner, ending), ..fields)
  } else if body.func() == sequence and body.children.len() > 0 {
    let children = body.children
    let last = children
      .rev()
      .position(it => it.func() not in ([ ].func(), parbreak))
    if last == none { join-pieces((body, ending)) } else {
      let index = children.len() - last - 1
      keep-label(body, join-pieces((
        ..children.slice(0, index),
        append-ending(children.at(index), ending),
        ..children.slice(index + 1),
      )))
    }
  } else { body + ending }
}

// A statement is a run of ordinary paragraphs with a little extra space
// around it, as in the book, not a block of its own: then Typst's paragraph
// indent works as in the book. The statement's head is indented like a new
// paragraph, so is the paragraph after the statement, while text that
// continues a sentence after a display formula stays flush left (a block
// would break the chain of paragraphs and lose the first two indents).
//
// Typst does not indent a paragraph that follows a display. A statement
// starts a new paragraph even there, so its first paragraph is indented
// always (`all: true`, the amount of book-style.typ); the rest of the
// statement follows the ordinary rule.
#let indent-first(body) = {
  let styled(it) = {
    set par(first-line-indent: (amount: 1.25em, all: true))
    it
  }
  let breaks(it) = (
    it.func() in (parbreak, block, grid, table, figure, list, enum, terms)
      or (it.func() == math.equation and it.block)
  )
  if body.func() == sequence and body.children.len() > 0 {
    let end = body.children.position(breaks)
    if end == none { styled(body) } else {
      join-pieces((
        styled(join-pieces(body.children.slice(0, end))),
        ..body.children.slice(end),
      ))
    }
  } else { styled(body) }
}

// The space around a statement is the paragraph spacing and a little more.
// It is weak and collapses with the paragraph spacing and with the space of
// a neighbouring statement, so two statements in a row are as far apart as
// a statement and a paragraph, not twice as far.
#let statement-space = context v(par.spacing + 0.35em, weak: true)
#let statement-block(body) = {
  statement-space
  let display = if body.func() == sequence {
    body.children.position(it => it.func() == math.equation and it.block)
  }
  let intro = if display != none { body.children.slice(0, display) }
  if intro != none {
    while intro.len() > 0 and intro.last().func() in ([ ].func(), parbreak) {
      intro = intro.slice(0, -1)
    }
  }
  if intro != none and intro.all(it => it.func() != parbreak) {
    // Keep a statement's opening paragraph with its first display. The
    // paragraphs remain native and the rest can still break normally.
    context block(sticky: true, above: 0pt, below: par.spacing, {
      indent-first(join-pieces(intro))
      parbreak()
    })
    join-pieces(body.children.slice(display))
  } else { indent-first(body) }
  parbreak()
  statement-space
}

// A formula of the Reference Chapter stated in words, "(F1) The number of roots
// …": `#formula-item[The number of roots …] <eq:number-of-roots>`. It shares
// the counter of the displays. Each item is a new statement, printed as a
// paragraph without extra space: its first line is indented like a
// statement's, also after a display.
#let formula-item(body) = {
  indent-first(prepend-heading(body, counted("eq", n => [(#n) ])))
  parbreak()
}

// A real form of an exceptional Lie algebra in Cartan's notation, "EVI",
// "FII", "G": `#real-form("EVI")`. The letter is the type, italic like $E_6$;
// the numeral is upright, as the text of the book prints it (Chapter 5, § 4,
// and the table of indices in § 1 of the Reference Chapter; the tables of § 2
// set the whole label in italic).
#let real-form(name) = {
  math.equation(math.italic(name.first()))
  text(style: "normal", name.slice(1))
}

// "Problem 16" linked to the problem's hint, if it has one. A hint leaves
// the full number of its problem (`hint` below). The link, or its absence,
// is recorded for the check of the PDF (`hint-link`, scripts/check_links.py).
#let hint-link(from, number, target) = metadata((
  kind: "hint-link",
  from: from,
  number: number,
  position: here().position(),
  target-position: if target != none { target.position() },
))
#let problem-words(words, number) = context {
  let hints = query(metadata.where(value: (
    kind: "hint",
    family: "pr",
    number: number,
  )))
  let target = if hints.len() == 1 { hints.first().location() }
  hint-link("problem", number, target)
  if target == none { words } else { link(target, words) }
}

// A statement that is both a problem and a corollary: "Problem 8 (Corollary
// 2).", `#problem(corollary: true)[…] <pr:cartan-k-theta-fixed-points>`, or
// "Corollary 2 (Problem 28).", `#corollary(problem: true)[…]
// <cor:semisimple-group-complete-reducibility>`. The label of its second role
// follows it on the next line: `#as-corollary
// <cor:cartan-k-theta-fixed-points>`, `#as-problem
// <pr:semisimple-group-complete-reducibility>` names the statement's record of
// that family just before (numbering.typ). The only corollary of a theorem is
// unnumbered and needs no second label.
#let alias(family) = context [#metadata((
  kind: "alias",
  family: family,
))<numbered>]
#let as-corollary = alias("cor")
#let as-problem = alias("pr")

// Problems are the backbone of the book. The number of a problem that has a
// hint links to the hint, and the hint's number links back. `title` is set
// in parentheses, "Problem 20 (Lemma)."; a problem that is a corollary of
// the theorem before it is titled with the corollary's number, "Problem 8
// (Corollary 2).", or "Problem 20 (Corollary)." (`as-corollary`).
// `numbered: false` gives the unnumbered "Problem." (the Translator's
// Preface).
#let problem(title: none, corollary: false, numbered: true, body) = {
  if not numbered {
    return statement-block(prepend-heading(body, [#strong[Задача.] ]))
  }
  let head = {
    family-counter("pr").step()
    if corollary { family-counter("cor").step() }
    context {
      let number = object-number("pr", here())
      record("pr")
      if corollary { record("cor") }
      let title = if not corollary { title } else {
        let own = object-number("cor", here())
        [Следствие#if own != none [ #own.last()]]
      }
      problem-words(
        strong[Задача #number.last()#if title != none [ (#title)].],
        number,
      )
      [ ]
    }
  }
  statement-block(prepend-heading(body, head))
}

// Theorem-like statements: bold head, italic body. `numbered: false` gives the
// unnumbered form ("Lemma."); `title` is set after the number in parentheses,
// "Theorem 5 (Lie's theorem)."; `prime: [@th:coset-conjugacy-by-normalizer]`
// (a reference, so that the editor goes to Theorem 4) is a restatement of
// that theorem, printed with its number and a prime, "Theorem 4′.", and not
// counted. A theorem or a proposition starts a group of
// corollaries.
#let theorem-like(kind, family, title, numbered, prime, body) = {
  let prime = if prime != none { str(references-in(prime).first()) }
  let head = {
    if numbered and prime == none { family-counter(family).step() }
    if numbered and family in ("th", "prop", "lem") {
      family-counter("cor").update(0)
    }
    context {
      record(family, prime: prime, unnumbered: not numbered)
      let shown = if numbered {
        object-number(family, here(), prime: prime).map(str).join(".")
      }
      text(style: "normal")[#strong[#kind#if shown != none [ #shown]]#if (
          title != none
        ) [ (#title)]#strong[.]]
      [ ]
    }
  }
  // A list or table set as a grid inside the statement is upright, as
  // printed (the lists of Theorems 5 and 6 of Chapter 5, § 1).
  show grid: set text(style: "normal")
  show table: set text(style: "normal")
  show math.equation.where(block: true): set block(sticky: true)
  text(style: "italic", statement-block(prepend-heading(body, head)))
}

#let theorem(title: none, numbered: true, prime: none, body) = theorem-like(
  "Теорема",
  "th",
  title,
  numbered,
  prime,
  body,
)
#let lemma(title: none, numbered: true, body) = theorem-like(
  "Лемма",
  "lem",
  title,
  numbered,
  none,
  body,
)
#let sublemma(body) = theorem-like("Подлемма", "lem", none, false, none, body)
#let proposition(title: none, numbered: true, body) = theorem-like(
  "Предложение",
  "prop",
  title,
  numbered,
  none,
  body,
)

// Corollaries are numbered after their theorem ("Corollary 2 of Theorem 3"),
// unnumbered when the theorem has only one. A corollary that is also a problem,
// "Corollary 2 (Problem 28).", takes `problem: true` and is followed by
// `#as-problem <pr:semisimple-group-complete-reducibility>`: it is then Problem
// 28 for references and hints.
#let corollary(title: none, problem: false, numbered: auto, body) = {
  let head = {
    if numbered != false { family-counter("cor").step() }
    if problem { family-counter("pr").step() }
    context {
      record("cor", unnumbered: numbered == false)
      let own = if numbered != false { object-number("cor", here()) }
      let problem-part = if problem {
        let number = object-number("pr", here())
        [
          (#record("pr")#problem-words([Задача #number.last()], number))]
      }
      text(style: "normal")[#strong[Следствие#if own != none [
            #own.last()]#problem-part]#if title != none [ (#title)]#strong[.]]
      [ ]
    }
  }
  text(style: "italic", statement-block(prepend-heading(body, head)))
}

// The proof ends with a square. In the book the square is printed after
// some proofs only; here every proof has it. The word joiner keeps it on
// the line of the last word.
#let qed-mark = [#sym.wj#box[#h(0.4em)$square.stroked$]]

// `head` replaces "Proof.": `#proof(head: [_Proof of the theorem._])`, or
// `head: none` for an argument the book gives without a heading but closes
// like a proof ("The theorem is proved. □").
#let proof(body, head: emph[Доказательство.], qed: true, equations: none) = {
  let body = if qed { append-ending(body, qed-mark) } else { body }
  let shown = statement-block(if head == none { body } else {
    prepend-heading(body, [#head ])
  })
  if equations == none { shown } else {
    let parent = references-in(equations)
    assert(parent.len() == 1, message: "Name the statement of the proof")
    context {
      let previous = equation-scope.get()
      let previous-count = proof-equations.get()
      equation-scope.update(parent.first())
      proof-equations.update(0)
      shown
      proof-equations.update(previous-count)
      equation-scope.update(previous)
    }
  }
}

// Numbered example in a list: `#eg <exm:circle-group>` prints "3)", Example 3
// of the current subsection (referred to as "Example 1.3").
#let eg = counted("exm", n => [#n)])

// Numbered example with a body and the book's parenthesized number.
#let example-item(body) = statement-block(prepend-heading(
  body,
  counted("exm", n => [(#n) ]),
))

// The first item of a second list of examples in one subsection, which the
// book numbers from 1 again (Chapter 1, § 1, 3°). Such a list is never
// referred to: its items carry no labels.
#let eg-restart = {
  family-counter("exm").update(0)
  section-examples.update(0)
  context [#metadata((
    kind: "restart",
    family: "exm",
    scope: place-key(here()),
  ))]
  eg
}

// A standalone numbered example paragraph: "Example 5. …".
#let example(body) = statement-block(prepend-heading(
  body,
  counted("exm", n => [#emph[Example #n.] ]),
))

// Hanging numbered item of the exercises and hints lists: the number
// right-aligned in the margin on the baseline of the first line (even when
// that line holds a tall formula), the text, its further paragraphs and
// displays aligned after it.
#let hanging-width = 2em
#let hanging-gap = 0.45em
#let hanging-item(number-text, body) = block(
  above: 0.7em,
  below: 0.7em,
  width: 100%,
  pad(left: hanging-width, {
    set par(first-line-indent: 0pt)
    let number = box(width: hanging-width - hanging-gap, h(1fr) + number-text)
    prepend-heading(body, h(-hanging-width) + number + h(hanging-gap))
    parbreak()
  }),
)

// Bibliography entry: `#bib-item[…] <bib:Jacobson1964>`,
// the printed text and the key of the entry in references.bib, in the order
// of the printed list. The number is not written: it counts the entries
// and is the number of `@bib:Jacobson1964`.
#let bib-item(body) = hanging-item(
  counted("bib", n => [#n.]),
  reference-rules(body, bibliographic-mention: false),
)

// Tables of the Reference Chapter. `#table-section[Decomposition of Tensor
// Products …] <tab:tensor-product-decompositions>` opens the description of a
// table: a heading in the contents ("Table 5. …", as printed there) and the
// target of `Table @tab:tensor-product-decompositions`.
#let table-section(title) = {
  family-counter("tab").step()
  context {
    record("tab")
    let n = object-number("tab", here()).last()
    heading(level: 3, numbering: none, supplement: [Table])[Table #n.
      #title]
  }
}

// The body of the current table (after its `table-section`) flows over our
// pages: `#book-table(columns: …, head: (…), ..cells)` is a Typst table
// whose header (`table.header`, repeated on every page the table spans) is
// the caption and the column heads `head`. The caption is "Table 5" on the
// first page of the table and "Table 5 (cont.)" on each later page, as the
// book prints its parts; the number is the current table's.
//
// A table printed as several blocks with their own column heads (Table 1:
// the roots, then the fundamental weights; Table 9: the two pages of each
// spread) is a run of `book-table`s. A block that begins on a page where an
// earlier block of its table stands takes no caption: that page has one. So
// every page of a table carries the caption at its top and none in mid-page.
// The caption left out is hidden, not removed, so the blocks keep the same
// height whatever the pages turn out to be.
// Each header placed on a page records its table and page in the state
// `table-headers`; a caption compares them with the record of the header
// before it.
//
// Subheads inside a table are headers of a higher level, `table.header(level:
// 2, …)`: Typst repeats them under the caption while their rows continue on
// the next page, until the next header of the same or a lower level (Table
// 7: "Type II"; Table 5: "Λ | dim R(Λ)", ended by the framed head of the next
// type, a header that does not repeat). Two headers of one level must not
// follow each other without a row between them (Typst 0.15.1 fails on that).
// Rows are not split between pages (book-style.typ), so a block of formulas
// or a diagram stays whole.
#let table-headers = state("table-headers", none)
#let book-table(columns: 1, head: (), ..cells) = context {
  let number = object-number("tab", here()).last()
  // The caption in the size of the text, as printed, not of the table.
  let size = text.size
  let count = if type(columns) == int { columns } else { columns.len() }
  let caption = table.cell(
    colspan: count,
    inset: 0pt,
    align: center,
    // The rule under the caption is the top of a table framed without inner
    // rules at the top of a page (Table 5); in a ruled table it is the top
    // rule of the column heads.
    stroke: (top: none, left: none, right: none, bottom: 0.5pt),
    context {
      let page = here().page()
      let before = table-headers.get()
      let cont = before != none and before.table == number
      let caption = pad(bottom: 0.6em, text(size: size)[Table #number#if (
          cont
        ) [ (cont.)]])
      // A caption left out keeps its place: the layout must not depend on
      // the pages it reads, or the document does not converge (Typst
      // documentation, "Convergence").
      if not cont or before.page != page { caption } else { hide(caption) }
      table-headers.update((table: number, page: page))
    },
  )
  table(columns: columns, table.header(caption, ..head), ..cells)
}

// A part of a table printed sideways in the book (Tables 3, 8, 10): turned
// to read from the bottom, centred on the page, running heads upright. Such
// a part is one page, as printed, with its caption at the top (the header of
// its `book-table`).
#let sideways(body) = align(center, rotate(-90deg, reflow: true, body))

// The book's figure: `#book-figure(drawing) <fig:rank-one-two-root-systems>`
// floats to the top or bottom of a page like the printed one, is captioned
// "Fig. 1" and is the target of `Fig.~@fig:rank-one-two-root-systems`. The
// record sits inside the float, so a link leads to where the figure is
// actually placed.
#let book-figure(body) = {
  family-counter("fig").step()
  figure(
    [#record("fig")#body],
    caption: context [Fig. #object-number("fig", here()).last()],
    numbering: none,
    placement: auto,
    supplement: none,
  )
}

// Section-closing lists. Each wraps its items and sets the heading.
#let exercises(body) = {
  heading(level: 3, numbering: none, outlined: true)[Exercises]
  body
}

#let exercise(body) = hanging-item(counted("exc", n => [#n)]), body)

#let hints(body) = {
  heading(level: 3, numbering: none, outlined: true)[Hints to Problems]
  body
}

// A hint names its problem by a reference to it, so that the editor goes
// from the hint to the problem:
// `#hint[@pr:differential-is-algebra-homomorphism][…]`, or
// `#hint[@pr:commutative-group-zero-bracket, @pr:tangent-algebra-of-gl][…]`
// for one hint to two problems ("1, 2."). The references are not printed as
// written: the hint prints the problems' counted numbers linked to them and
// leaves a record with the problem's full number, through which the
// problem's number links to the hint. A hint referred to ("Hint to
// Problem @hint:singular-elements-affine-hyperplanes") carries its own label
// after the body, `<hint:singular-elements-affine-hyperplanes>`, and has the
// number of its problem. A hint without its problem prints "?" unlinked; the
// lint reports it (rule T012).
#let hint(problems, body) = {
  let targets = references-in(problems)
  assert(
    targets.len() > 0 and targets.all(t => str(t).starts-with("pr:")),
    message: "A hint names its problems by references, #hint[@pr:…][…]: "
      + repr(problems),
  )
  hanging-item(
    context {
      let links = targets.map(target => {
        let found = numbered-record(target)
        let number = if found == none { ("?",) } else { record-number(found) }
        [#metadata((kind: "hint", family: "pr", number: number))<numbered>]
        let shown = str(number.last())
        if found == none { shown } else {
          // Each number leads back to the head of its problem.
          context {
            hint-link("hint", number, found.location())
            link(found.location(), shown)
          }
        }
      })
      [#links.join[, ].]
    },
    body,
  )
}

// Definitions in this book are unnumbered.
#let definition(body) = statement-block(
  prepend-heading(body, [#text(style: "normal", weight: "bold")[Определение.]
  ]),
)
#let remark(body) = statement-block(
  prepend-heading(body, [#emph[Remark.] ]),
)

// Native list markers and these records advance in the same item order.
// A question's semantic label attaches to the whole helper call.
#let question-list(body) = {
  family-counter("item").update(0)
  body
}
#let question(body) = {
  family-counter("item").step()
  [#record("item")#body]
}

// Parts of one statement, with native enum markers and semantic references.
#let part-list(body) = {
  family-counter("part").update(0)
  set enum(numbering: "(1)")
  body
}
#let statement-part(body) = {
  family-counter("part").step()
  [#record("part")#body]
}
