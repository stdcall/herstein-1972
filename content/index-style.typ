// Index locators use the named object when supplied, including its page.
#import "numbering.typ": numbered-record

#let sort-key(path) = {
  lower(path.join(" "))
    .replace(regex("\\s*\\([^)]*\\)"), "")
    .replace(regex("[,’'.]"), "")
}

#let entry-text(path, previous) = {
  let parts = ()
  let shared = previous != none
  for (i, part) in path.enumerate() {
    if shared and i < previous.len() and previous.at(i) == part {
      parts.push("—")
    } else {
      parts.push(part)
      shared = false
    }
  }
  parts.join(", ")
}

// Alternate word order and inflection do not create duplicate articles.
// Original index marks remain unchanged; their locators are combined here.
#let subject-aliases = (
  "Гипотеза Кёте": ("Кёте гипотеза",),
  "Группа когомологий": ("Когомологий группа",),
  "Двойного централизатора теорема": (
    "Теорема о двойном централизаторе",
  ),
  "Лемма Шура": ("Шура лемма",),
  "Кольцо частных": ("Частных кольцо",),
  "Познера теорема": ("Познера теоремы",),
  "Теорема Машке": ("Машке теорема",),
  "Теорема плотности": ("Плотности теорема",),
  "Система факторов > нормализованные": (
    "Система факторов",
    "нормализованная",
  ),
)

#let canonical-path(path, index) = if index == "subject" {
  subject-aliases.at(path.join(" > "), default: path)
} else { path }

#let index-target(mark) = {
  let target = mark.value.at("target", default: none)
  if target == none {
    return (at: mark.location(), target: "index-mark", resolved: true)
  }
  let elements = query(target)
  if elements.len() != 1 {
    return (at: mark.location(), target: str(target), resolved: false)
  }
  let record = numbered-record(target)
  let at = if record != none { record.location() } else {
    elements.first().location()
  }
  (at: at, target: str(target), resolved: true)
}

#let locator(destination) = box(context {
  metadata((
    kind: "cross-reference",
    target: destination.target,
    resolved: destination.resolved,
    position: here().position(),
    target-position: destination.at.position(),
  ))
  let number = str(counter(page).at(destination.at).first())
  if destination.resolved { link(destination.at, number) } else { "?" }
})

#let index-entries(index) = context {
  let marks = query(<index-mark>).filter(it => (
    it.value.at("index", default: "subject") == index
  ))
  let entries = (:)
  for mark in marks {
    let path = canonical-path(mark.value.path, index)
    let key = if index == "subject" { sort-key(path) } else {
      path.join("\u{1f}")
    }
    let entry = entries.at(key, default: (path: path, at: ()))
    if path.len() > entry.path.len() { entry.path = path }
    let destination = index-target(mark)
    let number = counter(page).at(destination.at).first()
    if entry.at.all(d => counter(page).at(d.at).first() != number) {
      entry.at.push(destination)
    }
    entries.insert(key, entry)
  }
  let previous = none
  let initial = none
  for entry in entries.values().sorted(key: e => sort-key(e.path)) {
    let letter = upper(sort-key(entry.path).first())
    if letter != initial {
      if initial != none { v(0.6em, weak: true) }
      initial = letter
      previous = none
    }
    let shown = entry-text(entry.path, previous)
    block(above: 0pt, below: 0.25em, par(hanging-indent: 1.2em)[
      #shown #entry.at.map(locator).join([, ])
    ])
    previous = entry.path
  }
}

#let book-index(title, index: "subject") = {
  heading(numbering: none, title)
  set par(first-line-indent: 0pt, justify: false, leading: 0.45em)
  set text(size: 10pt)
  columns(2, gutter: 8mm, index-entries(index))
}
