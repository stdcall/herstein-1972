// Source boundaries, semantic references, index marks and notation.

#import "numbering.typ": (
  equation-scope, numbered-record, place-key, record-number, reference-chapter,
)
#import "name-index-data.typ": index-name

#let editorial-notes = sys.inputs.at("editorial-notes", default: "on") != "off"

#let russian-typography(body) = {
  show regex("\\b[А-ЯЁа-яё]\\.(?: +[А-ЯЁа-яё]\\.)+"): it => {
    it.text.replace(" ", "\u{00a0}")
  }
  body
}

#let printed-offset = -1

#let partitioned(delim: "(", ..rows) = math.mat(
  delim: delim,
  augment: (hline: 1, vline: 1),
  ..rows.pos(),
)

#let source(n, printed: none) = context {
  let printed = if printed == none { str(n - printed-offset) } else {
    printed
  }
  [#metadata((
    kind: "source",
    file-page: n,
    printed-page: printed,
    position: here().position(),
  ))]
}

#let number-text(body) = text(weight: "semibold", style: "normal", body)

#let relative-number(key, here-key) = {
  let limit = calc.min(key.len() - 1, here-key.len())
  let common = 0
  while common < limit and key.at(common) == here-key.at(common) {
    common += 1
  }
  key.slice(common).join(".")
}

#let reference-body(it, caption, bibliographic-mention: true) = context {
  let target = str(it.target)
  let prefix = target.split(":").first()
  let here-key = place-key(here()).map(str)
  let record = if it.element != none { numbered-record(it.target) }
  let number = if record != none { record-number(record) }
  let descriptive = caption and it.element != none
  let pending = number == none and not descriptive
  let printed = if number == none {
    if descriptive { "" } else { "?" }
  } else if (
    prefix in ("bib", "cor")
      or it.supplement == []
      or (
        prefix == "eq"
          and record != none
          and equation-scope.at(here()) != none
          and equation-scope.at(here()) == equation-scope.at(record.location())
      )
  ) { str(number.last()) } else {
    number.map(str).join(".")
  }
  let body = if caption { it.supplement } else if prefix in ("eq", "part") {
    let letter = printed.match(regex("^[A-Z]$")) != none
    text(style: "normal")[(#number-text(
        if letter { emph(printed) } else { printed },
      ))]
  } else if (
    prefix == "ss"
      and not pending
      and (
        not printed.contains(".") or it.supplement == [°]
      )
  ) { number-text(printed + "°") } else { number-text(printed) }
  let destination = if pending { none } else if (
    it.element.func() == math.equation
  ) { it.element.location() } else if record != none {
    record.location()
  } else { it.element.location() }
  [#metadata((
    kind: "cross-reference",
    target: target,
    bibliographic-mention: bibliographic-mention,
    resolved: not pending,
    printed: printed,
    position: here().position(),
    target-position: if not pending { destination.position() },
  ))<cross-reference>]
  if pending { body } else { sym.wj + link(destination, body) }
}

#let reference-rules(body, bibliographic-mention: true) = {
  show ref: it => {
    let caption = it.supplement not in (auto, none, [], [°])
    let shown = reference-body(
      it,
      caption,
      bibliographic-mention: bibliographic-mention,
    )
    if caption { shown } else { box(shown) }
  }
  body
}

#let idx(..path, target: none, index: "subject") = {
  assert(path.named().len() == 0 and path.pos().len() > 0)
  let path = path.pos()
  if index == "name" { path = path.map(index-name) }
  [#metadata((
    kind: "index-mark",
    path: path,
    target: target,
    index: index,
  ))<index-mark>]
}

#let semantic-block(body) = block(body)

#let editorial-note-counter = counter("editorial-note")
#let ed-note(body) = if editorial-notes {
  editorial-note-counter.step()
  context {
    let mark = "*" + str(editorial-note-counter.get().first()) + ")"
    footnote(numbering: _ => mark)[#body~— _Прим. ред._]
    counter(footnote).update(n => n - 1)
  }
}

#let mathclap(body) = context {
  let content = $script(body)$
  let width = measure(content).width
  box(width: 0pt, inset: (left: -width / 2, right: -width / 2), content)
}

#let group-name(name) = math.class("normal", math.upright(name))
#let GL = group-name("GL")
#let SL = group-name("SL")
#let PGL = group-name("PGL")
#let PSL = group-name("PSL")
#let SO = group-name("SO")
#let SU = group-name("SU")
#let Sp = group-name("Sp")
#let GA = group-name("GA")
#let Spin = group-name("Spin")

#let Ad = math.op("Ad")
#let ad = math.op("ad")
#let Aut = math.op("Aut")
#let Int = math.op("Int")
#let Der = math.op("Der")
#let Diff = math.op("Diff")
#let Ker = math.op("Ker")
#let tr = math.op("tr")
#let Im = math.op("Im")
#let rk = math.op("rk")
#let codim = math.op("codim")
#let Hom = math.op("Hom")
#let End = math.op("End")
#let Lie = math.op("Lie")
#let Sq = math.op("Sq")
#let Id = math.op("Id")
#let Gr = math.op("Gr")
#let bold(body) = math.upright(math.bold(body))
#let rad = math.op(math.frak("rad"))
#let der = math.op(math.frak("der"))
#let Rad = math.op("Rad")
#let trdeg = math.op("tr. deg")
#let diag = math.op("diag")
#let Re = math.op("Re")
#let char = math.op("char")
#let id = math.op(math.italic("id"))

#let bordered(..rows) = context {
  let (top, ..body) = rows.pos()
  let labels = body.map(row => row.first())
  let cells = body.map(row => row.slice(1))
  let width(it) = measure(math.equation(it)).width
  let matrix = math.mat(..cells)
  let bare = width(math.mat(delim: none, ..cells))
  let side = math.mat(
    delim: none,
    ..labels.zip(cells).map(((label, row)) => (label, ..row.map(hide))),
  )
  let back = h(0.4em - bare)
  let over((j, label)) = {
    let column = calc.max(..cells.map(row => width(row.at(j))))
    box(width: column, align(center, math.equation(label)))
  }
  let head = math.mat(delim: none, top.slice(1).enumerate().map(over))
  let paren = h((width(matrix) - bare) / 2)
  $#side #back limits(#matrix)^(#paren #head #paren)$
}
