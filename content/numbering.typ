// Separate section-local statement and equation counters.
// Chapter 8 has no sections and uses section 1 for its statements.

#let sectionless-chapters = (8,)

#let place-key(location) = {
  let numbers = counter(heading).at(location)
  let chapter = numbers.at(0, default: 0)
  let section = numbers.at(1, default: 0)
  let subsection = numbers.at(2, default: 0)
  if chapter in sectionless-chapters { section = 1 }
  (chapter, section, subsection)
}

#let reference-chapter = -1

#let family-depth = (
  pr: 2,
  th: 2,
  lem: 2,
  prop: 2,
  exc: 2,
  eq: 2,
  exm: 2,
  cor: 2,
  tab: 0,
  fig: 0,
  bib: 0,
  item: 0,
  part: 0,
)

#let examples-through-section = ()

#let formula-skips = (:)

#let formula-tags = (:)

#let family-counter(family) = counter("numbered:" + family)
#let section-examples = counter("numbered:exm-section")
#let equation-scope = state("equation-scope", none)
#let proof-equations = counter("numbered:proof-equations")

#let restart-counters(level) = {
  for (family, depth) in family-depth {
    if depth >= level { family-counter(family).update(0) }
  }
  if level <= 2 { section-examples.update(0) }
}

#let corollary-place(location) = {
  let starts = ("th", "prop", "lem")
  let parent = query(selector(<numbered>).before(location))
    .rev()
    .find(it => it.value.at("family", default: none) in starts)
  if parent == none { return (none, none) }
  let group = 0
  for it in query(selector(<numbered>).after(parent.location())) {
    let family = it.value.at("family", default: none)
    if family in starts and it.location() != parent.location() { break }
    if (
      family == "cor"
        and it.value.kind == "numbered"
        and not it.value.at("unnumbered", default: false)
    ) { group += 1 }
  }
  if group < 2 { return (parent, none) }
  (parent, family-counter("cor").at(location).first())
}

#let numbered-record(target) = {
  if query(target).len() != 1 { return none }
  let record = query(selector(<numbered>).within(target)).at(0, default: none)
  if record != none and record.value.kind == "alias" {
    let family = record.value.family
    record = query(selector(<numbered>).before(record.location()))
      .rev()
      .find(it => (
        it.value.kind == "numbered"
          and it.value.at("family", default: none) == family
      ))
  }
  record
}

#let object-number(
  family,
  location,
  prime: none,
  tag: none,
  unnumbered: false,
) = {
  if unnumbered { return none }
  let scope = place-key(location).slice(0, family-depth.at(family))
  let statement-number(record) = object-number(
    record.value.family,
    record.location(),
    prime: record.value.at("prime", default: none),
  )
  if family == "cor" {
    let (parent, n) = corollary-place(location)
    if n == none { return none }
    return (..statement-number(parent), n)
  }
  if tag != none { return (..scope, tag) }
  if prime != none {
    let base = numbered-record(label(prime))
    let number = if base == none { (..scope, "?") } else {
      statement-number(base)
    }
    return (..number.slice(0, -1), str(number.last()) + "′")
  }
  let n = family-counter(family).at(location).first()
  if family == "eq" {
    let parent = equation-scope.at(location)
    if parent != none {
      let parent-record = numbered-record(parent)
      assert(parent-record != none, message: "Equation scope needs a statement")
      return (
        ..statement-number(parent-record),
        proof-equations.at(location).first(),
      )
    }
  }
  if family == "exm" and scope.slice(0, 2) in examples-through-section {
    n = section-examples.at(location).first()
  }
  let own = if family == "eq" and scope.first() == reference-chapter {
    "F" + str(n)
  } else { n }
  (..scope, own)
}

#let record-number(record) = {
  let value = record.value
  if value.at("unnumbered", default: false) { return none }
  if value.kind == "hint" { return value.number }
  if value.family == "heading" {
    return place-key(record.location()).slice(0, value.level)
  }
  object-number(
    value.family,
    record.location(),
    prime: value.at("prime", default: none),
    tag: value.at("tag", default: none),
  )
}

#let record(family, ..flags) = context [#metadata((
  kind: "numbered",
  family: family,
  ..flags.named(),
  number: object-number(family, here(), ..flags.named()),
))<numbered>]
