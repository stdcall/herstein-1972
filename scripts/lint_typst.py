"""Project lint: conservative source checks plus Typst's evaluated document.

No fixes: mathematical meaning and source readings must never change
implicitly. This is not a general Typst parser or a mathematical proof checker.

Rules. Findings are errors unless marked otherwise; a warning is printed and
does not fail the lint.

  T000  upstream tools: tinymist lint, typstyle --check, typst eval
  T001  final newline, Unicode NFC, trailing whitespace, tabs, CR
  T002  control characters, soft hyphens, zero-width spaces or Cyrillic
        outside comments
  T003  unresolved markers (TODO, FIXME, ???, ...)
  T004  line longer than max_line_length; a line that holds only a range of
        references, `Exercises~@exc:a–@exc:b`, which Typstyle cannot break,
        may be longer (`@` references keep the editor's navigation)
  T005  the editor passes the same stage input as config/project.json
  T010  labels: allowed prefix and a semantic name (lowercase words and
        digits joined by hyphens, with a letter: no number), duplicates; the
        shared labels that the helpers set on their records (<numbered>,
        <index-mark>) are not written by hand
  T011  headings in chapter files: no typed numbers ("§ 2.", "1°.",
        "Chapter 1"); a numbered heading carries its label (= <ch:…>,
        == <sec:…>, === <ss:…>)
  T012  numbered objects: every environment of a numbered family is followed
        by its label (`#theorem[…] <th:levi-subalgebra-exists>`); in the
        evaluated document
        every numbered object is reached by a label of its family, every
        label reaches one, and every hint names an existing problem. Items
        of a list of examples restarted with #eg-restart are not referred to
        and need no label
  T013  formula numbers come from <eq:…> labels on displays only
  T014  unresolved cross-references: error in final; in draft they are
        listed in <cache>/unresolved-references.json; a reference to a
        label that no chapter file sets: warning in draft, error in final
  T015  source-page anchors #source(N): unique and in the order of the pages
        of the source edition
  T016  bibliography: an entry is `#bib-item[…] <bib:Key>` with the key of
        references.bib; every @bib:Key names an entry of the list (an error
        in draft too: the list is complete)
  T017  numbers are counted, never written: an environment takes no number
        (`#theorem(4)`, `#eg(3)`, `#table-section(5)`), a hint names its
        problem by reference (`#hint[@pr:…][…]`), and no head is typed by
        hand ("*Theorem 3.*", "_Example 5._", "(F1)" opening a paragraph)
  T018  references are Typst's own `@` references (`@pr:…`; in a formula
        `#[@eq:…]`), not string wrappers such as `#pr(16)`, `#eqref(17)`,
        `#bib("Borel1956")`, nor labels passed as arguments, `#ref(<…>)`,
        `#link(<…>)`, `#hint(<pr:…>)`, `prime: <th:…>`: the editor does not
        follow those to the target
  T020-T025  Typst mathematics pitfalls
  T030  literal reference to a numbered object ("Problem 12", "Theorem 5")
  T031  literal formula number ("(17)", "formula (1.2)")
  T032  literal bibliography number ("[34]"): the message names the key
  T033  literal section, subsection or chapter number ("§ 3", "2.9", "6°",
        "Chapter 4")
        T030-T033: a reference @pr:…, @eq:…, @ss:…, @bib:Key,
        ... links and checks the target and prints its counted number. A
        number that belongs to another work ("Theorem 3 of [16]") is listed
        in literal_references.
  T040  chapter files carry no layout: no set/show rules, includes, manual
        spacing or breaks, joiners, boxes, lr(size: ...); documented
        exceptions in local_markup
  T041  semicolon after an embedded call is swallowed by the code
  T042  line starting with "3." becomes an enumeration item
  T043  prose line ending in a hyphen: a word broken at the line end
  T044  #source(...) on its own line splits a sentence into two paragraphs
  T050  subject index marks
  T099  unused exception in config/lint.json
"""
from collections import Counter, defaultdict
import bisect
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata

from check_indexes import index_checks
from project import (settings, formatter_command, tool_env, cache_path,
                     editor_settings, stage, typst_inputs)

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- scanning

MARKUP, CITED, MATH, CODE, STRING, COMMENT, RAW = 'mbxcs/r'
IDENT = re.compile(r'[A-Za-z_][\w-]*')
STATEMENTS = {'let', 'set', 'show', 'import', 'include', 'if', 'for',
              'while', 'return', 'context', 'break', 'continue'}


def scan(text, cited=()):
    """Classify every character of a Typst file by the mode it is read in.

    Returns (kinds, ends): `kinds[i]` is MARKUP (prose), MATH, CODE, STRING,
    COMMENT or RAW; markup inside the content blocks of a helper named in
    `cited` (the bibliography entries) is CITED. `ends` holds the offsets
    just after each embedded expression (`#pr(16)`, `#problem(1)[...]`).
    A small scanner, not a parser: it follows markup, math and code far
    enough to tell prose from code and mathematics, which regular
    expressions over the raw file cannot.
    """
    n = len(text)
    kinds = [MARKUP] * n
    ends = set()
    # Frames: [mode, closer, cited]. Modes: markup, math, code (closer ')'
    # or '}'), line (a statement up to the end of its line), expr (just
    # after '#'), post (after a call name: arguments, content, fields).
    stack = [['markup', None, False, None]]

    def mark(start, end, kind):
        for j in range(start, min(end, n)):
            kinds[j] = kind

    def comment_end(i):
        if text.startswith('//', i):
            j = text.find('\n', i)
            return n if j < 0 else j
        depth, j = 1, i + 2
        while j < n and depth:
            if text.startswith('/*', j):
                depth, j = depth + 1, j + 2
            elif text.startswith('*/', j):
                depth, j = depth - 1, j + 2
            else:
                j += 1
        return j

    def string_end(i):
        j = i + 1
        while j < n:
            if text[j] == '\\':
                j += 2
            elif text[j] == '"':
                return j + 1
            else:
                j += 1
        return n

    def is_comment(i, mode):
        if text.startswith('/*', i):
            return True
        if not text.startswith('//', i):
            return False
        # "https://..." in markup is a link, not a comment.
        return not (mode == 'markup' and i and text[i-1] == ':')

    def starts_expression(i):
        return i < n and (IDENT.match(text, i) is not None
                          or text[i] in '([{')

    i = 0
    while i < n:
        mode, closer, quoted, name = stack[-1]
        ch = text[i]
        if mode == 'expr':
            match = IDENT.match(text, i)
            if match:
                mark(i, match.end(), CODE)
                i = match.end()
                if match.group() in STATEMENTS:
                    stack[-1] = ['line', '\n', quoted, None]
                else:
                    stack[-1] = ['post', None, quoted, match.group()]
                continue
            stack[-1] = ['post', None, quoted, None]
            continue
        if mode == 'post':
            if ch in '({':
                kinds[i] = CODE
                stack.append(['code', ')' if ch == '(' else '}',
                              quoted or name in cited, None])
                i += 1
                continue
            if ch == '[':
                kinds[i] = CODE
                stack.append(['markup', ']', quoted or name in cited, 'arg'])
                i += 1
                continue
            if ch == '.' and i + 1 < n and IDENT.match(text, i + 1):
                match = IDENT.match(text, i + 1)
                mark(i, match.end(), CODE)
                i = match.end()
                continue
            stack.pop()
            ends.add(i)
            continue
        if mode in ('code', 'line'):
            if is_comment(i, mode):
                j = comment_end(i)
                mark(i, j, COMMENT)
                i = j
                continue
            if ch == '"':
                j = string_end(i)
                mark(i, j, STRING)
                i = j
                continue
            kinds[i] = CODE
            if ch == closer:
                stack.pop()
            elif ch in '({':
                stack.append(['code', ')' if ch == '(' else '}', quoted, None])
            elif ch == '[':
                stack.append(['markup', ']', quoted, 'arg'])
            elif ch == '$':
                stack.append(['math', '$', quoted, None])
            i += 1
            continue
        if mode == 'math':
            if is_comment(i, mode):
                j = comment_end(i)
                mark(i, j, COMMENT)
                i = j
                continue
            if ch == '\\':
                mark(i, i + 2, MATH)
                i += 2
                continue
            if ch == '"':
                j = string_end(i)
                mark(i, j, STRING)
                i = j
                continue
            if ch == '#' and starts_expression(i + 1):
                kinds[i] = CODE
                stack.append(['expr', None, quoted, None])
                i += 1
                continue
            kinds[i] = MATH
            if ch == '$':
                stack.pop()
            i += 1
            continue
        # markup
        prose = CITED if quoted else MARKUP
        if is_comment(i, mode):
            j = comment_end(i)
            mark(i, j, COMMENT)
            i = j
            continue
        if ch == '\\':
            mark(i, i + 2, prose)
            i += 2
            continue
        if ch == '`':
            run = len(re.match(r'`+', text[i:]).group())
            if run == 2:
                j = i + 2
            else:
                j = text.find('`' * run, i + run)
                j = n if j < 0 else j + run
            mark(i, j, RAW)
            i = j
            continue
        if ch == '$':
            kinds[i] = MATH
            stack.append(['math', '$', quoted, None])
            i += 1
            continue
        if ch == '#' and starts_expression(i + 1):
            kinds[i] = CODE
            stack.append(['expr', None, quoted, None])
            i += 1
            continue
        if ch == '[':
            kinds[i] = prose
            stack.append(['markup', ']', quoted, 'text'])
            i += 1
            continue
        if ch == ']' and closer == ']':
            kinds[i] = CODE if name == 'arg' else prose
            stack.pop()
            i += 1
            continue
        kinds[i] = prose
        i += 1
    return kinds, ends


def view(text, kinds, keep, fill=' ', placeholders=None):
    """Text with the characters of other kinds replaced; newlines kept."""
    placeholders = placeholders or {}
    out = []
    for ch, kind in zip(text, kinds):
        if ch == '\n' or kind in keep:
            out.append(ch)
        else:
            out.append(placeholders.get(kind, fill))
    return ''.join(out)


# Prose view for the literal-reference rules: code and strings become \x01
# (a helper call stands where a number would), mathematics \x02, raw \x03.
PROSE_PLACEHOLDERS = {CODE: '\x01', STRING: '\x01', MATH: '\x02', RAW: '\x03'}


def prose_view(text, kinds):
    """Prose of a file for the literal-reference rules. Labels (`<eq:…>`)
    and references (`@x`) are markup but not prose; headings are checked by
    T011 and carry no references."""
    prose = view(text, kinds, (MARKUP,), placeholders=PROSE_PLACEHOLDERS)
    return re.sub(r'(?m)<[A-Za-z][\w:.-]*>|@[A-Za-z][\w:.-]*|^[ \t]*=+[ \t].*$',
                  lambda m: ' ' * len(m.group()), prose)


def line_of(text, offset):
    return text.count('\n', 0, offset) + 1


# ------------------------------------------------------------ label forms

# A label is a semantic name that says what the object is: lowercase words
# and digits joined by hyphens, with at least one letter
# (th:levi-subalgebra-exists, eq:number-of-roots); it holds no number, the
# number is counted.
NAME = r'(?=[a-z0-9-]*[a-z])[a-z0-9]+(?:-[a-z0-9]+)*'
LABEL_FORMS = {prefix: NAME for prefix in (
    'ch', 'sec', 'ss', 'pr', 'th', 'lem', 'prop', 'cor', 'exc', 'hint', 'exm',
    'eq', 'tab', 'fig', 'part', 'term', 'def', 'display', 'front', 'item')}
LABEL_FORMS |= {
    # Bibliography keys: surname of the first author and year, a/b/c for
    # one author and year (Borel1956, Dynkin1952a); references.bib.
    'bib': r'[A-Z][A-Za-z]*[0-9]{4}[a-z]?',
    # The shared labels: every index mark carries <index-mark>
    # (main-defs.typ), every record of a numbered object <numbered>
    # (numbering.typ).
    'index-mark': r'',
    'numbered': r'',
    'cross-reference': r'',
}
# Labels that the helpers set; the chapter files write all others at their
# objects.
SET_BY_HELPERS = ('index-mark', 'numbered', 'cross-reference')
# Environments of the numbered families and the prefix of their labels.
ENVIRONMENTS = {'problem': 'pr', 'theorem': 'th', 'lemma': 'lem',
                'proposition': 'prop', 'corollary': 'cor', 'example': 'exm',
                'eg': 'exm', 'exercise': 'exc', 'table-section': 'tab',
                'book-figure': 'fig', 'formula-item': 'eq', 'bib-item': 'bib',
                'as-corollary': 'cor', 'as-problem': 'pr'}
ENVIRONMENTS['question'] = 'item'
ENVIRONMENTS['sublemma'] = 'term'
ENVIRONMENTS['statement-part'] = 'part'
ENVIRONMENTS['example-item'] = 'exm'
# String wrappers of references that the chapter files used before native
# references (rule T018).
REFERENCE_WRAPPERS = ('pr', 'th', 'lem', 'prop', 'exc', 'hint-ref', 'exm',
                      'cor', 'eqref', 'ss', 'sect', 'chap', 'tab', 'fig',
                      'bib')
# A source line that is one range of references and nothing else (rule
# T004): an optional reference word tied to it, `Exercises~`, and the book's
# ")" after item numbers, "Exercises 5)–14)".
REFERENCE_RANGE_LINE = re.compile(
    r'[ \t]*(?:[A-Za-z]+~)?@[\w:-]+\)?–@[\w:-]+\)?[.,;:]?[ \t]*')
# Heading level -> the prefix of its label.
HEADING_PREFIX = {1: 'ch', 2: 'sec', 3: 'ss'}


def label_problem(name):
    if name in SET_BY_HELPERS:
        return None
    # Established keys without a dated edition retain their names.
    if name in (
            'bib:BirkhoffMacLane', 'bib:HersteinTopics',
            'bib:VanDerWaerdenModern'):
        return None
    prefix, _, rest = name.partition(':')
    if prefix not in LABEL_FORMS:
        return (f'label <{name}> has no allowed prefix ('
                + ', '.join(sorted(LABEL_FORMS)) + ')')
    if not re.fullmatch(LABEL_FORMS[prefix], rest):
        return f'label <{name}> does not have the form of a {prefix}: label'
    return None


# ------------------------------------------------------------ source rules

class Exceptions:
    """Documented exceptions: {file: {phrase: reason}} from config/lint.json.

    A finding is excused when it lies inside an occurrence of the phrase in
    that file (whitespace-insensitive), so the entry names the place, not
    just the number: "Theorem 3 of #bib(16)", not "Theorem 3".
    """

    def __init__(self, config, key):
        self.key = key
        self.entries = config.get(key, {})
        self.used = set()
        self.spans = {}

    @staticmethod
    def flatten(text):
        """The text as one line, and the offset of each character in `text`.
        Runs of whitespace become one space; an argument list reads as on one
        line, so the formatter's split of a long call, `#bib(\\n "Key",\\n)`,
        still matches the phrase `#bib("Key")`."""
        flat, where = [], []
        for offset, ch in enumerate(text):
            if ch.isspace():
                if not flat or flat[-1] in ' (':
                    continue
                ch = ' '
            if ch == ')':
                while flat and flat[-1] == ' ':
                    flat.pop()
                    where.pop()
                if flat and flat[-1] == ',':
                    flat.pop()
                    where.pop()
            flat.append(ch)
            where.append(offset)
        return ''.join(flat), where

    def _spans(self, path, text):
        if path not in self.spans:
            flat, where = self.flatten(text)
            spans = []
            for phrase, reason in self.entries.get(path, {}).items():
                wanted = self.flatten(phrase)[0].strip()
                if not wanted or not str(reason).strip():
                    continue
                for m in re.finditer(re.escape(wanted), flat):
                    spans.append((where[m.start()], where[m.end() - 1] + 1,
                                  phrase))
            self.spans[path] = spans
        return self.spans[path]

    def excuses(self, path, text, start, end):
        for first, last, phrase in self._spans(path, text):
            if first <= start and end <= last:
                self.used.add((path, phrase))
                return True
        return False

    def unused(self):
        return [{'rule': 'T099', 'path': 'config/lint.json', 'line': None,
                 'message': f'{self.key}: unused exception {phrase!r} for '
                            f'{path} (no such place, or the reason is empty)'}
                for path, phrases in self.entries.items()
                for phrase in phrases if (path, phrase) not in self.used]


REFERENCE_WORDS = (r'Problems?|Theorems?|Lemmas?|Propositions?|Exercises?'
                   r'|Examples?|Tables?|Hints?|Corollary|Corollaries'
                   r'|[Тт]еорем(?:а|ы|е|у|ой)?|[Лл]емм(?:а|ы|е|у|ой)?'
                   r'|[Пп]редложени(?:е|я|ю|ем)|[Сс]ледстви(?:е|я|ю|ем)'
                   r'|[Зз]адач(?:а|и|е|у)|[Пп]ример(?:а|ы|е|у)?')
LITERAL_ITEM = r'\d+(?:\.\d+)*[a-z]?(?![\w.]\d)'
ITEM = r'(?:\x01+|' + LITERAL_ITEM + r')'
SEPARATOR = r'(?:[ \t~]*(?:,|\band\b|\bor\b|\bto\b|\bи\b|\bили\b|[–—-])[ \t\n~]*)'
REFERENCE_LIST = re.compile(
    r'\b(' + REFERENCE_WORDS + r')[ \t\n~]+(' + ITEM
    + r'(?:' + SEPARATOR + ITEM + r')*)')


def bibliography_keys(root=ROOT):
    """Keys of the printed bibliography in its order: entry n is keys[n-1]."""
    path = root/'content/89-bibliography.typ'
    if not path.is_file():
        return []
    text = path.read_text()
    kinds, _ = scan(text)
    uncommented = view(text, kinds, (MARKUP, CITED, MATH, CODE, STRING, RAW))
    return re.findall(r'<bib:([^>]+)>', uncommented)


def literal_reference_checks(path, text, prose, literal):
    """T030-T033 over the prose of a chapter file."""
    findings, taken = [], []

    def add(rule, start, end, message):
        # An excused place is still taken: "Theorem 3.2 of [16]" must
        # not come back as the section number "3.2".
        taken.append((start, end))
        if literal.excuses(path, text, start, end):
            return
        findings.append({'rule': rule, 'path': path,
                         'line': line_of(text, start), 'message': message})

    def overlaps(start, end):
        return any(a < end and start < b for a, b in taken)

    prefix = {'Problem': 'pr', 'Theorem': 'th', 'Lemma': 'lem',
              'Proposition': 'prop', 'Exercise': 'exc', 'Example': 'exm',
              'Table': 'tab', 'Hint': 'hint', 'Corollary': 'cor'}
    for m in REFERENCE_LIST.finditer(prose):
        word = m.group(1).rstrip('s')
        word = 'Corollary' if word.startswith('Corollar') else word
        russian = {'теорем': 'th', 'лемм': 'lem', 'предложени': 'prop',
                   'следстви': 'cor', 'задач': 'pr', 'пример': 'exm'}
        family = next((value for key, value in russian.items()
                       if word.lower().startswith(key)), prefix.get(word))
        for item in re.finditer(LITERAL_ITEM, m.group(2)):
            start = m.start(2) + item.start()
            add('T030', start, m.start(2) + item.end(),
                f'Literal reference "{word} {item.group()}": write {word} '
                f'@{family}:<key> (the label of the object) so the '
                'number is counted and linked (a number in another work goes '
                'to literal_references)')
    for m in re.finditer(r'(?<![\w\x01\x02)\]])\(\s*(\d{1,3}(?:\.\d{1,3})*'
                         r'[a-z]?)\s*\)', prose):
        # "(1) the inverse image ..." opening a paragraph labels an item of
        # a list of statements; a reference to it later is still reported.
        line_start = prose.rfind('\n', 0, m.start()) + 1
        previous = prose[prose.rfind('\n', 0, max(line_start - 1, 0)) + 1:
                         max(line_start - 1, 0)]
        if not prose[line_start:m.start()].strip() and not previous.strip():
            continue
        add('T031', m.start(), m.end(),
            f'Literal formula number "{m.group()}": write @eq:<key> (it '
            'prints the parentheses)')
    keys = bibliography_keys()
    for m in re.finditer(r'\\?\[\s*(\d{1,3}(?:\s*,\s*\d{1,3})*)\s*'
                         r'(,[^\]\n]*)?\\?\]', prose):
        cited = [f'@bib:{keys[n - 1]}' if 0 < n <= len(keys) else '@bib:?'
                 for n in map(int, re.findall(r'\d+', m.group(1)))]
        loc = ', ...' if m.group(2) else ''
        add('T032', m.start(), m.end(),
            f'Literal bibliography number "{m.group()}": write '
            f'[{", ".join(cited)}{loc}] (the key of references.bib; the '
            'number is counted in the list)')
    patterns = (
        (r'§[ \t~]*\d+(?:\.\d+)*', 'write §~@sec:<key>'),
        (r'(?<![\w.])\d{1,2}(?:\.\d{1,2}){0,2}[ \t]*°', 'write @ss:<key>'),
        (r'\bChapters?[ \t\n~]+\d+', 'write Chapter @ch:<key>'),
        (r'\b[Гг]лав(?:а|ы|е|у|ой)[ \t\n~]+\d+', 'write глава @ch:<key>'),
        (r'(?<![\w.\x01\x02])\d{1,2}\.\d{1,2}(?:\.\d{1,2})?'
         r'(?![\w°\x01\x02]|\.\d)', 'write @ss:<key>, @sec:<key> or the '
         'reference to the object'),
    )
    for pattern, advice in patterns:
        for m in re.finditer(pattern, prose):
            if overlaps(m.start(), m.end()):
                continue
            add('T033', m.start(), m.end(),
                f'Literal section/subsection/chapter number '
                f'"{m.group().strip()}": {advice}')
    return findings


LAYOUT_CODE = re.compile(
    r'#(?:set|show|include|pagebreak|colbreak|linebreak|h|v|box|block|text'
    r'|pad|place|move|hide|scale|rotate)\b|sym\.wj\b')
# Typst math functions: `times.r_upright("Id")` is a call in the subscript by
# intent, unlike `T_x(X)`, where the letter swallows the argument (T020).
MATH_FUNCTIONS = {
    'upright', 'italic', 'bold', 'serif', 'sans', 'frak', 'mono', 'bb', 'cal',
    'scr', 'op', 'lr', 'mid', 'abs', 'norm', 'floor', 'ceil', 'round', 'sqrt',
    'root', 'frac', 'binom', 'vec', 'mat', 'cases', 'accent', 'hat', 'tilde',
    'overline', 'underline', 'overbrace', 'underbrace', 'overbracket',
    'underbracket', 'dot', 'dash', 'macron', 'breve', 'acute', 'grave',
    'arrow', 'cancel', 'display', 'inline', 'script', 'sscript', 'text',
    'class', 'limits', 'scripts', 'stretch', 'attach', 'primes', 'overparen',
    'underparen', 'overshell', 'undershell'}

# In mathematics a single letter is a letter, so h(t) is a function; the
# spacing function is reached only as #h(...), which is code.
LAYOUT_MATH = re.compile(r'\blr\(\s*size\s*:|(?<![\w.])wj\b')


def layout_checks(path, text, kinds, local):
    """T040: no layout policy and no local spacing hacks in chapter files."""
    findings = []
    code = view(text, kinds, (CODE,))
    math = view(text, kinds, (MATH,))
    for source, pattern in ((code, LAYOUT_CODE), (math, LAYOUT_MATH)):
        for m in pattern.finditer(source):
            if local.excuses(path, text, m.start(), m.end()):
                continue
            findings.append({
                'rule': 'T040', 'path': path, 'line': line_of(text, m.start()),
                'message': f'{m.group().strip()!r} in a chapter file: layout '
                           'belongs to book-style.typ/main-defs.typ as a global '
                           'rule; a justified one-off goes to local_markup'})
    return findings


def heading_checks(path, text, markup):
    """T011: headings type no numbers, and a numbered heading carries its
    label: `== Tangent Algebra <sec:lie-group-tangent-algebra>` (a long
    heading: the label alone on the next line)."""
    findings = []
    for m in re.finditer(r'(?m)^[ \t]*(=+)[ \t]+(.*)$(?:\n[ \t]*(<[\w:.-]+>)'
                         r'[ \t]*$)?', markup):
        body = m.group(2) + (m.group(3) or '')
        level = len(m.group(1))
        labels = re.findall(r'<([\w:.-]+)>', body)
        wanted = HEADING_PREFIX.get(level)
        if len(labels) != 1 or labels[0].split(':')[0] != wanted:
            findings.append({
                'rule': 'T011', 'path': path, 'line': line_of(text, m.start()),
                'message': f'A numbered heading of level {level} carries its '
                           f'label <{wanted}:...> at its end (found '
                           f'{labels or "none"})'})
        title = re.sub(r'<[\w:.-]+>', '', body).strip()
        if re.match(r'(?:§|Chapter\s+[0-9IVX]|\d+\s*°|\d+(?:\.\d+)*\.?\s)',
                    title):
            findings.append({
                'rule': 'T011', 'path': path, 'line': line_of(text, m.start()),
                'message': f'Heading {title!r} types its number; the style '
                           'numbers headings'})
    return findings


def closing(text, kinds, start):
    """Offset of the bracket that closes the one at `start` (code
    parentheses; brackets of content blocks)."""
    opening = text[start]
    close = {'(': ')', '[': ']'}[opening]
    counted = (CODE,) if opening == '(' else (MARKUP, CITED, CODE)
    depth, i = 0, start
    while i < len(text):
        kind, ch = kinds[i], text[i]
        if kind in (MARKUP, CITED) and ch == '\\':
            i += 2
            continue
        if kind in counted:
            if ch == opening:
                depth += 1
            elif ch == close:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return len(text) - 1


def call_end(text, kinds, i):
    """Offset after the arguments and content blocks of the call whose name
    ends at `i`."""
    while i < len(text) and text[i] in '([' and kinds[i] == CODE:
        i = closing(text, kinds, i) + 1
    return i


def numbering_source_checks(path, text, kinds, ends):
    """T012 (static part), T017, T018 over a chapter file."""
    findings = []

    def add(rule, offset, message):
        findings.append({'rule': rule, 'path': path,
                         'line': line_of(text, offset), 'message': message})
    code = view(text, kinds, (CODE,))
    markup = view(text, kinds, (MARKUP, CITED))
    names = '|'.join(sorted(ENVIRONMENTS, key=len, reverse=True))
    restarted = False
    calls = re.finditer(r'(?m)^[ \t]*(=+)[ \t]|#(' + names + r'|eg-restart)'
                        r'(?![\w-])', text)
    for m in calls:
        if m.group(1):
            if kinds[m.start(1)] == MARKUP:
                restarted = False
            continue
        if kinds[m.start()] != CODE:
            continue
        name = m.group(2)
        if name == 'eg-restart':
            restarted = True
            continue
        end = call_end(text, kinds, m.end())
        call = text[m.start():end]
        arguments = ''
        if text[m.end():m.end() + 1] == '(':
            arguments = text[m.end() + 1:closing(text, kinds, m.end())]
        if re.match(r'\s*(?:[0-9]|"|none\b)', arguments):
            add('T017', m.start(), f'#{name} takes no number: the number is '
                f'counted; write #{name}[…] <{ENVIRONMENTS[name]}:key>')
            continue
        if name == 'corollary' or 'numbered: false' in arguments \
                or (name == 'eg' and restarted):
            # A corollary is numbered only with others (the evaluated check
            # T012 asks for its label then).
            continue
        after = re.match(r'\s*<([\w:.-]+)>', text[end:])
        wanted = ENVIRONMENTS[name]
        if not after or after.group(1).split(':')[0] != wanted:
            add('T012', m.start(), f'#{name} is not followed by its label '
                f'<{wanted}:key>: every numbered object carries its label')
    for m in re.finditer(r'#eg\(', code):
        add('T017', m.start(), '#eg takes no number: write #eg <exm:key>')
    for m in re.finditer(r'#hint\[\s*(?:[0-9]|")', text):
        add('T017', m.start(), 'A hint names its problem by reference: '
            '#hint[@pr:key][…]')
    heads = (r'(?:Theorem|Lemma|Proposition|Corollary|Problem|Example'
             r'|Exercise|Definition|Remark|Hint|Теорема|Лемма|Предложение'
             r'|Следствие|Задача|Пример|Определение|Замечание|Указание)')
    for m in re.finditer(r'[*_][ \t]*' + heads + r'[ \t]+[0-9IVX]+[′\']?\.?'
                         r'[ \t]*[*_]', markup):
        add('T017', m.start(), f'Typed head {m.group().strip()!r}: use the '
            'environment, which counts the number')
    for m in re.finditer(r'(?m)^[ \t]*\(F[0-9]+\)[ \t]', markup):
        add('T017', m.start(), f'Typed number {m.group().strip()!r} opening a '
            'paragraph: use #formula-item (or the environment of the object)')
    wrappers = '|'.join(sorted(REFERENCE_WRAPPERS, key=len, reverse=True))
    for m in re.finditer(r'#(' + wrappers + r')\(', code):
        add('T018', m.start(), f'#{m.group(1)}(...) is a string wrapper of a '
            'reference: write the native reference @prefix:key')
    for m in re.finditer(r'#(?:ref|link|hint)\(\s*\(?\s*<|\bprime\s*:\s*<',
                         code):
        add('T018', m.start(), f'{m.group().strip()!r}: a label passed as an '
            'argument; write an @ reference (`@a–@b`, `#hint[@pr:key][…]`, '
            '`prime: [@th:key]`) so that the editor goes to the target')
    return findings


def pitfall_checks(path, text, kinds, ends):
    """T041-T044: faults that read correctly in the source and only go wrong
    in the rendered PDF."""
    findings = []

    def add(rule, offset, message):
        findings.append({'rule': rule, 'path': path,
                         'line': line_of(text, offset), 'message': message})
    # "#pr(1); hence" prints without the ";": it ends the embedded code.
    for offset in sorted(ends):
        if offset < len(text) and text[offset] == ';' and \
                kinds[offset] in (MARKUP, CITED):
            add('T041', offset, 'Semicolon right after an embedded call is '
                'consumed as code and never printed; write #[;] or \\;')
    # A markup line that opens with "3." is parsed as an enumeration item,
    # so the number disappears from the sentence and starts a list instead.
    prose = (MARKUP, CITED)
    for m in re.finditer(r'(?m)^[ \t]*(\d+)\.(?=[ \t]|$)', text):
        if kinds[m.start(1)] in prose:
            add('T042', m.start(), f'Line starts with "{m.group(1)}." and is '
                'parsed as an enum item, dropping the number from the '
                f'sentence; escape it as {m.group(1)}\\.')
    # A trailing hyphen breaks a word at the end of the line; Typst would
    # print the hyphen and a space.
    for m in re.finditer(r'(?m)(?<![-\s])-$', text):
        if kinds[m.start()] in prose:
            add('T043', m.start(), 'Line ends with a hyphen that breaks a '
                'word; join the word')
    # #source(...) alone between blank lines splits the sentence it sits in
    # into two paragraphs; the marker belongs inline in the running text.
    lines = view(text, kinds, (MARKUP, CITED, MATH, CODE, STRING, RAW))
    lines = lines.split('\n')
    prose_lines = view(text, kinds, (MARKUP, CITED, MATH)).split('\n')
    raw_lines = text.split('\n')
    offset = 0
    for index, line in enumerate(lines):
        if re.match(r'^[ \t]*#source\(', line) and index \
                and not lines[index-1].strip():
            previous = next((p for p in reversed(prose_lines[:index-1])
                             if p.strip()), '').rstrip()
            previous_block = re.split(r'\n[ \t]*\n',
                                      '\n'.join(raw_lines[:index]).rstrip())[-1]
            completed_before_footnote = re.search(
                r'[.!?]\s*#footnote\[[\s\S]*\]\s*$', previous_block)
            rest = line.split(')', 1)[-1].strip()
            following = rest or next(
                (p.strip() for p in lines[index+1:] if p.strip()), '')
            prose_before = previous \
                and not re.search(r'[.!?:\]$>]$', previous) \
                and not completed_before_footnote \
                and not re.match(r'^[ \t]*(?:#(?:import|let|set|show)\b|=+ )',
                                 previous)
            prose_after = following and not re.match(r'^(=|#|\$\s)', following)
            if prose_before and prose_after:
                add('T044', offset, 'Source anchor on its own line splits a '
                    'sentence into two paragraphs; place it inline')
        offset += len(line) + 1
    return findings


def source_checks(path, text, config, exceptions):
    """Checks of one source file. Returns (findings, markup labels)."""
    findings = []

    def add(rule, offset, message):
        findings.append({'rule': rule, 'path': path,
                         'line': line_of(text, offset), 'message': message})
    if not text.endswith('\n'):
        add('T001', len(text), 'Missing final newline')
    if text != unicodedata.normalize('NFC', text):
        add('T001', 0, 'Use Unicode NFC')
    for m in re.finditer(r'[ \t]+(?=\n)|\t|\r', text):
        add('T001', m.start(), 'Trailing whitespace, tab or CR line ending')
    limit = config.get('max_line_length', 80)
    offset = 0
    for line in text.splitlines(keepends=True):
        width = len(line.rstrip('\r\n'))
        if width > limit and not REFERENCE_RANGE_LINE.fullmatch(
                line.rstrip('\r\n')):
            add('T004', offset, f'Line has {width} characters; maximum is '
                f'{limit}. Run just fmt; split long formulas explicitly.')
        offset += len(line)
    kinds, ends = scan(text, cited=set(config.get('cited_helpers', [])))
    uncommented = view(text, kinds, (MARKUP, CITED, MATH, CODE, STRING, RAW))
    for m in re.finditer(r'[\u0000-\u0008\u000b\u000c\u000e-\u001f\u00ad'
                         r'\u200b\ufeff\ufffd]', uncommented):
        add('T002', m.start(), 'Control or invisible character')
    for m in re.finditer(r'\b(?:TODO|FIXME|XXX|UNREADABLE)\b|\?\?\?',
                         uncommented):
        add('T003', m.start(), 'Unresolved marker')
    markup = view(text, kinds, (MARKUP, CITED))
    code = view(text, kinds, (CODE,))
    labels = []
    references = []
    chapter = re.fullmatch(config['chapter_files'], path) is not None
    # Labels written at their objects.
    written = [(m.start(), m.group(1)) for m in
               re.finditer(r'<([A-Za-z][\w:.-]*)>', markup)]
    for offset, name in sorted(written):
        labels.append((name, line_of(text, offset)))
        problem = label_problem(name)
        if problem:
            add('T010', offset, problem)
        elif chapter and name.split(':')[0] in SET_BY_HELPERS:
            add('T010', offset, f'<{name}> is set by a helper (the '
                'records of numbered objects, #idx); do not write it by '
                'hand')
    # References: all are native `@` references, also those by which a hint
    # names its problems and a restatement its theorem (`#hint[@pr:…][…]`,
    # `prime: [@th:…]`).
    for m in re.finditer(r'@([A-Za-z][\w:.-]*[\w])', markup):
        references.append((m.group(1), line_of(text, m.start())))
    math = view(text, kinds, (MATH,))
    for m in re.finditer(r'_([A-Za-z][A-Za-z0-9]*)\(', math):
        if m.group(1) in MATH_FUNCTIONS:
            continue
        add('T020', m.start(), 'Ambiguous subscript call; write T_x (X) or '
            'group the index explicitly')
    for m in re.finditer(r'\\(?:frac|dfrac|begin|end|sqrt|mathbb|mathfrak'
                         r'|mathbf|boldsymbol)\b', math):
        add('T021', m.start(), 'Unconverted LaTeX in Typst mathematics')
    for m in re.finditer(r'(?<![\w.])bar\(', math):
        add('T022', m.start(), 'bar() creates vertical fences; use overline() '
            'for a bar over the symbol or abs() for the absolute value')
    for m in re.finditer(r"_(?:[A-Za-z0-9]+|\([^()\n]*\))'+", math):
        add('T023', m.start(), "Prime attaches to the subscript; write "
            "phi'_X for a primed base or phi_(X') for a primed index")
    for m in re.finditer(r'\^[A-Za-z]\(', math):
        add('T024', m.start(), 'Ambiguous superscript call; separate the '
            'following factor or group the exponent explicitly')
    for m in re.finditer(r'\\\\(?=[ \t]*(?:\n|&))', math):
        add('T025', m.start(), 'LaTeX-style doubled linebreak; one backslash '
            'breaks a line in Typst mathematics')
    if chapter:
        prose = prose_view(text, kinds)
        findings.extend(literal_reference_checks(
            path, text, prose, exceptions['literal']))
        findings.extend(layout_checks(path, text, kinds, exceptions['local']))
        findings.extend(heading_checks(path, text, markup))
        findings.extend(pitfall_checks(path, text, kinds, ends))
        findings.extend(numbering_source_checks(path, text, kinds, ends))
    return findings, labels, references


# --------------------------------------------------------- evaluated rules

def plain(node):
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ''
    if node.get('func') == 'space':
        return ' '
    return node.get('text', '') + ''.join(
        plain(x) for x in node.get('children', []))


def label_name(item):
    # Typst prints a label that is not a plain identifier (a primed number,
    # "th:4.4.4′") as label("..."), not <...>.
    name = (item.get('label') or '').strip('<>')
    quoted = re.fullmatch(r'label\("(.*)"\)', name)
    return quoted.group(1) if quoted else name


def pt(value):
    return float(str(value).removesuffix('pt'))


def point(position):
    return (int(position['page']), pt(position['y']), pt(position['x']))


ROMAN = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'),
         (90, 'xc'), (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'), (5, 'v'),
         (4, 'iv'), (1, 'i')]


def to_roman(number):
    out = ''
    for value, letters in ROMAN:
        while number >= value:
            out, number = out + letters, number - value
    return out


def from_roman(text):
    text = text.lower()
    for number in range(1, 400):
        if to_roman(number) == text:
            return number
    return None


def section_file(root, key):
    """Chapter file of a section key "C.S" (content/CS-*.typ), if unique."""
    chapter, _, rest = key.partition('.')
    section = rest.split('.')[0]
    for prefix in (chapter + section, chapter + '0'):
        found = sorted((root/'content').glob(prefix + '-*.typ'))
        if len(found) == 1:
            return str(found[0].relative_to(root))
    return 'content/main.typ'


# The family of the record that a label of each prefix must reach; headings
# by their level.
HEADING_LEVEL = {'ch': 1, 'sec': 2, 'ss': 3}


def coverage_checks(data, static_labels, final):
    """T012: every label of a numbered family reaches a numbered object of
    its family (its record, numbering.typ), and every numbered object is
    reached by a label; every hint names an existing problem. `labelled`
    of the evaluated document maps each label written in the chapter files
    to the record it reaches."""
    findings = []

    def add(message, position=None, label=None):
        path, line = static_labels.get(label, ('content/main.typ', None))
        findings.append({'rule': 'T012', 'severity': 'error', 'path': path,
                         'line': line, 'page': (position or {}).get('page'),
                         'message': message})
    reached = set()
    for name, found in sorted((data.get('labelled') or {}).items()):
        prefix = name.partition(':')[0]
        if prefix in SET_BY_HELPERS or name == 'ch:reference':
            continue
        record = found['record']
        if prefix in ('part', 'term', 'def', 'display', 'front') and not (
                prefix == 'part' and record is not None
                and record['value'].get('family') == 'part'):
            if found['count'] != 1:
                add(f'<{name}> is set {found["count"]} times', label=name)
            continue
        if found['count'] != 1 or record is None:
            add(f'<{name}> is set {found["count"]} times or on no numbered '
                'object', label=name)
            continue
        value = record['value']
        if prefix in HEADING_LEVEL:
            fits = (value.get('family') == 'heading'
                    and value.get('level') == HEADING_LEVEL[prefix])
        elif prefix == 'hint':
            fits = value.get('kind') == 'hint'
        else:
            fits = value.get('family') == prefix
        if not fits:
            add(f'<{name}> is on {value.get("family") or value.get("kind")} '
                f'{value.get("number")}, not on an object of its family',
                record['position'], label=name)
        reached.add(point(record['position']))
    restarts = [(point(item['position']), tuple(item['value']['scope']))
                for item in data['metadata']
                if isinstance(item['value'], dict)
                and item['value'].get('kind') == 'restart']
    for item in data['metadata']:
        value = item['value']
        if label_name(item) != 'numbered' or not isinstance(value, dict):
            continue
        where = point(item['position'])
        if value.get('kind') == 'hint':
            if any(isinstance(n, str) for n in value.get('number', [])):
                add('A hint names no existing problem (Problem '
                    + '.'.join(map(str, value['number'])) + ')',
                    item['position'])
            continue
        number = value.get('number')
        if number is None or where in reached:
            continue
        if value.get('family') == 'exm' and any(
                start <= where and tuple(number[:3]) == scope
                for start, scope in restarts):
            continue
        add(f'{value.get("family")} {".".join(map(str, number))} carries no '
            'label: every numbered object carries its label (a corollary '
            'too, once its theorem has several)', item['position'])
    return findings


def semantic_checks(data, config, root, final, static_labels,
                    references=None):
    """Checks of the evaluated document. Labels written in the sources
    (`static_labels`) were checked there, with their lines; `references`
    maps each label that a chapter file refers to to its first place."""
    references = references or {}
    findings = []

    def add(rule, item, message, severity='error', label=None):
        position = (item or {}).get('position') or {}
        path, line = static_labels.get(label, ('content/main.typ', None))
        findings.append({'rule': rule, 'severity': severity, 'path': path,
                         'line': line, 'page': position.get('page'),
                         'message': message})
    labels = []
    for item in data['headings']:
        name = label_name(item)
        if name:
            labels.append(name)
    numbered_at = set()
    labelled_at = set()
    for item in data['equations']:
        name = label_name(item)
        if name:
            labels.append(name)
        if name.startswith('eq:'):
            if not item['block']:
                add('T013', item, f'<{name}> is on an inline formula; the '
                    'number is printed only on displays', label=name)
            else:
                labelled_at.add(point(item['position']))
        elif item['numbered'] and item['block']:
            numbered_at.add(point(item['position']))
    for where in sorted(numbered_at - labelled_at):
        add('T013', {'position': {'page': where[0]}}, 'Numbered display '
            'without an <eq:…> label: only labelled displays are numbered')
    sources = []
    for item in data['metadata']:
        value = item['value']
        if not isinstance(value, dict):
            continue
        name = label_name(item)
        if name:
            labels.append(name)
            problem = label_problem(name)
            if problem:
                add('T010', value, problem)
        kind = value.get('kind')
        if kind == 'cross-reference' and not value.get('resolved'):
            target = str(value.get('target'))
            if target.startswith('bib:'):
                add('T016', value, f'Citation of {target[4:]!r}: no entry '
                    'of the bibliography has this key (#bib-item[…] '
                    '<bib:Key> in 89-bibliography.typ, references.bib)')
            elif final:
                add('T014', value, f'Unresolved reference: {target}')
        if kind == 'source':
            page = value.get('file-page')
            sources.append(page)
            if not isinstance(page, int) or page < 1:
                add('T015', value, f'Source page {page!r} is not a page '
                    'number')
    if sources != sorted(set(sources)):
        repeated = sorted(p for p, c in Counter(sources).items() if c > 1)
        add('T015', None, 'Source-page anchors must be unique and in the '
            f'order of the source edition; repeated: {repeated}, order: '
            f'{sources}')
    for name, count in Counter(labels).items():
        if count > 1 and name not in static_labels \
                and name not in SET_BY_HELPERS:
            add('T010', None, f'Label <{name}> is set {count} times')
    findings.extend(coverage_checks(data, static_labels, final))
    # References to labels that no chapter file writes.
    for name, (path, line) in sorted(references.items()):
        if name in static_labels:
            continue
        severity = 'error' if final or name.startswith('bib:') else 'warning'
        findings.append({'rule': 'T016' if name.startswith('bib:') else 'T014',
                         'severity': severity, 'path': path, 'line': line,
                         'message': f'@{name}: no chapter file sets the label '
                                    f'<{name}>'})
    return findings


# -------------------------------------------------------------- the report

def unresolved_references(data, current_stage):
    """Cross-references whose target is missing, grouped by target, each
    occurrence with its PDF page and the page of the source edition it
    stands on (the last #source anchor before it)."""
    anchors = sorted(
        (point(item['value']['position'])[:2], item['value']['file-page'])
        for item in data['metadata']
        if isinstance(item['value'], dict)
        and item['value'].get('kind') == 'source')
    keys = [a for a, _ in anchors]
    targets = defaultdict(list)
    for item in data['metadata']:
        value = item['value']
        if isinstance(value, dict) and value.get('kind') == 'cross-reference' \
                and not value.get('resolved'):
            where = point(value['position'])[:2]
            index = bisect.bisect_right(keys, where) - 1
            targets[value['target']].append({
                'pdf_page': where[0],
                'source_page': anchors[index][1] if index >= 0 else None})
    return {'stage': current_stage,
            'count': sum(len(v) for v in targets.values()),
            'targets': [{'target': t, 'occurrences': targets[t]}
                        for t in sorted(targets)]}


def write_unresolved(root, data):
    report = unresolved_references(data, stage(root))
    path = cache_path(root)/'unresolved-references.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    return report, path


def input_hashes(root):
    paths = [root/'corrections.json',
             *sorted((root/'content').rglob('*.typ')),
             *sorted(root.glob('*.bib')),
             *sorted((root/'config').glob('*.json')),
             *sorted(p for p in (root/'assets').rglob('*') if p.is_file()),
             root/'.vscode/settings.json',
             *sorted((root/'scripts').glob('*.py'))]
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.is_file()}


def tool_versions(root=ROOT):
    return {name: subprocess.run([name, '--version'], capture_output=True,
                                 text=True).stdout.strip()
            for name in settings(root)['tool_versions']}


EXPRESSION = '''(
  headings: query(heading).map(it => (
    label: it.at("label", default: none), level: it.level,
    numbered: it.numbering != none, body: it.body,
    position: it.location().position())),
  equations: query(math.equation).filter(it => it.block or it.has("label"))
    .map(it => (label: it.at("label", default: none), block: it.block,
      numbered: it.numbering != none, position: it.location().position())),
  metadata: query(metadata).map(it => (
    label: it.at("label", default: none), value: it.value,
    position: it.location().position())),
)'''


# For each label written in the chapter files: how often it is set and the
# record of the numbered object it reaches (numbering.typ).
LABELLED = '''{
  import "/content/numbering.typ": numbered-record
  LABELS.map(name => {
    let record = numbered-record(label(name))
    (name, (
      count: query(label(name)).len(),
      record: if record != none {
        (value: record.value, position: record.location().position())
      },
    ))
  }).to-dict()
}'''


def evaluate(root=ROOT, *, notes=True, labels=None):
    """The evaluated document: headings, displays and all metadata, and for
    `labels` (the labels written in the chapter files) the records they
    reach (`labelled`).

    Returns (process, data); data is None when the evaluation failed.
    """
    expression = EXPRESSION
    if labels:
        names = '(' + ', '.join(json.dumps(name, ensure_ascii=False)
                               for name in labels) + ',)'
        head = EXPRESSION.rstrip()[:-1].rstrip().rstrip(',')
        expression = (head + ',\n  labelled: '
                      + LABELLED.replace('LABELS', names) + ',\n)')
    result = subprocess.run(
        ['typst', 'eval', *typst_inputs(root, notes=notes), expression,
         '--in', settings(root)['entry'], '--format', 'json'],
        cwd=root, env=tool_env(root), capture_output=True, text=True)
    return result, (json.loads(result.stdout) if result.returncode == 0
                    else None)


def lint(root=ROOT):
    cache_path(root).mkdir(parents=True, exist_ok=True)
    config = json.loads((root/'config/lint.json').read_text())
    current_stage = stage(root)
    final = current_stage == 'final'
    findings = []
    hashes = input_hashes(root)
    versions = tool_versions(root)
    upstream = []
    inputs = typst_inputs(root)
    commands = [
        ['tinymist', 'lint', '--diagnostic-format', 'short', '--root',
         str(root), *inputs, settings(root)['entry']],
        formatter_command(root, check=True),
    ]
    for cmd in commands:
        if not shutil.which(cmd[0]):
            findings.append({'rule': 'T000', 'path': 'content/main.typ',
                             'message': f'Missing {cmd[0]}; install with '
                                        'brew install tinymist typstyle'})
            continue
        checked = subprocess.run(cmd, cwd=root, env=tool_env(root),
                                 capture_output=True, text=True, timeout=300)
        output = checked.stdout + checked.stderr
        upstream.append({'command': cmd, 'exit_code': checked.returncode,
                         'diagnostics': output,
                         'version': versions.get(cmd[0])})
        if checked.returncode or re.search(r'(?:^|: )(?:warning|error):',
                                           output, re.M):
            findings.append({'rule': 'T000', 'path': 'content/main.typ',
                             'message': f'{cmd[0]} failed: {output.strip()}'})
    extra = editor_settings(root).get('tinymist.typstExtraArgs', [])
    wanted = '--input=stage=' + current_stage
    if wanted not in extra:
        findings.append({'rule': 'T005', 'path': '.vscode/settings.json',
                         'message': f'tinymist.typstExtraArgs must contain '
                                    f'"{wanted}" (config/project.json stage), '
                                    'so the editor builds what the CLI builds'})
    exceptions = {'literal': Exceptions(config, 'literal_references'),
                  'local': Exceptions(config, 'local_markup')}
    # Labels written in the chapter files: name -> (path, line) of the first;
    # references likewise.
    static_labels = {}
    references = {}
    for path in (p for p in hashes if p.endswith('.typ')):
        errors, labels, referred = source_checks(
            path, (root/path).read_text(), config, exceptions)
        findings.extend(errors)
        if re.fullmatch(config['chapter_files'], path) is None:
            continue
        for name, line in referred:
            references.setdefault(name, (path, line))
        for name, line in labels:
            if name in static_labels:
                first = ':'.join(map(str, static_labels[name]))
                findings.append({'rule': 'T010', 'path': path, 'line': line,
                                 'message': f'Duplicate label {name}; first '
                                            f'in {first}'})
            else:
                static_labels[name] = (path, line)
    for listed in exceptions.values():
        findings.extend(listed.unused())
    result, data = evaluate(root, labels=sorted(static_labels))
    if result.returncode or result.stderr.strip():
        findings.append({'rule': 'T000', 'path': 'content/main.typ',
                         'message': result.stderr.strip()
                         or 'Typst evaluation failed'})
    unresolved = None
    if data is not None:
        findings.extend(semantic_checks(data, config, root, final,
                                        static_labels, references))
        errors, warnings = index_checks(data['metadata'], final=final)
        findings.extend({'rule': 'T050', 'path': 'content/main.typ',
                         'message': e} for e in errors)
        findings.extend({'rule': 'T050', 'severity': 'warning',
                         'path': 'content/main.typ', 'message': w}
                        for w in warnings)
        unresolved, unresolved_path = write_unresolved(root, data)
    for item in findings:
        item.setdefault('severity', 'error')
    errors = [f for f in findings if f['severity'] == 'error']
    warnings = [f for f in findings if f['severity'] != 'error']
    report = {
        'status': 'failed' if errors else 'passed',
        'stage': current_stage,
        'fingerprint': {'sources': hashes, 'tools': versions,
                        'stage': current_stage},
        'scope': 'source+evaluated document', 'input_sha256': hashes,
        'upstream': upstream, 'errors': errors, 'warnings': warnings,
        'counts': {
            'source_files': sum(p.endswith('.typ') for p in hashes),
            'static_labels': len(static_labels),
            # Displays of the text, not the numbered copies of the style.
            'display_equations': sum(
                x['block'] and (bool(x['label']) or not x['numbered'])
                for x in data['equations'])
            if data else None,
            'headings': len(data['headings']) if data else None,
            'unresolved_references': unresolved['count']
            if unresolved else None}}
    (cache_path(root)/'typst-lint.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if data is not None:
        (cache_path(root)/'document.json').write_text(
            json.dumps(data, ensure_ascii=False) + '\n')
    for item in warnings + errors:
        where = item['path']
        if item.get('line'):
            where += f':{item["line"]}'
        elif item.get('page'):
            where += f' (PDF page {item["page"]})'
        tag = item['rule'] + (' warning' if item['severity'] != 'error'
                              else '')
        print(f'{where}: {tag}: {item["message"]}')
    if unresolved and unresolved['count']:
        print(f'{unresolved["count"]} unresolved references to '
              f'{len(unresolved["targets"])} targets '
              f'({current_stage}: listed in {unresolved_path})')
    print(json.dumps({'lint': report['status'], 'stage': current_stage,
                      'errors': len(errors), 'warnings': len(warnings),
                      **report['counts']}))
    return report
