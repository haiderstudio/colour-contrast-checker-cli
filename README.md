# colour-contrast-checker-cli

Check colour contrast against WCAG AA and AAA, fail CI on a fail.

[![CI](https://github.com/haiderstudio/colour-contrast-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/colour-contrast-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`colour_contrast_checker` reads hex colour pairs and reports the
WCAG contrast ratio and an AA / AAA pass or fail for each pair. It
exits 0 when every pair passes the level you asked for and 1 when
any pair fails, so it can fail a CI run.

- It takes pairs from a CSS file (each rule's `color` against its
  `background-color`), from a pairs file (`foreground background
  [label]`, one per line), or from two hex colours on the command
  line.
- It checks normal text by default (AA 4.5:1, AAA 7:1). `--large`
  uses the large-text limits instead (AA 3:1, AAA 4.5:1).
- `--level aaa` fails on anything below AAA; the default `--level
  aa` fails on anything below AA.
- It is report-only: it never changes a CSS file, and it sends
  nothing anywhere — it runs fully offline.

## What it does NOT do

- It does not fix your CSS. A failing pair is reported, not
  rewritten.
- It does not check a whole website, crawl pages, or run a browser.
  One CSS file or one list of pairs at a time.
- It does not guess colours it cannot read. Named colours (`red`),
  `rgb()`, and `var()` are skipped and reported as skipped — a rule
  with a colour but no background is skipped the same way, instead
  of being checked against an invented background.
- It does not check colour blindness, font sizes, or anything other
  than the WCAG contrast ratio.

## Who it is for

Anyone who writes CSS and wants a quick, scriptable check that
their text can be read: a developer adding a CI step, a designer
handing over a stylesheet, or anyone fixing contrast on one page.
If the check passes, the pairs are readable at that level; if it
fails, the report says exactly which pair and by how much.

## How this differs from similar tools

Colour contrast checkers already exist, and most of them are web
pages or desktop apps: WebAIM's contrast checker and Snook's
colour contrast tool check two colours in a browser, and
Pushedskydiver/Colour-Contrast-Checker (173 stars) is a TypeScript
web app. The command-line ones are JavaScript: @siluat's
color-contrast-cli and wcag-contrast-cli check one pair at a time
and need Node.js. The Python option, gsnedders/wcag-contrast-ratio,
is a library for computing ratios, not a CLI, and it does not read
CSS or fail CI. Full-site tools like axe-core and pa11y check
contrast as one of many things, inside a whole audit.

This tool does a narrower job: a Python standard-library-only CLI
that reads a CSS file or a list of hex pairs, reports AA/AAA per
pair, and exits 1 on a fail — no install beyond Python, no browser,
no Node, no library to wire up.

## Install

Python standard library only — no packages to download. Clone the
repo and run it in place:

```sh
git clone https://github.com/haiderstudio/colour-contrast-checker-cli.git
cd colour-contrast-checker-cli
```

Python 3.10 or newer.

## Usage

Check a CSS file:

```sh
python3 src/colour_contrast_checker.py examples/sample.css
```

Real output:

```text
PASS  body                          #111111 on #ffffff  18.88:1  AA PASS  AAA PASS
PASS  a                             #333333 on #ffffff  12.63:1  AA PASS  AAA PASS
PASS  .muted                        #767676 on #ffffff   4.54:1  AA PASS  AAA FAIL
FAIL  .faint                        #777777 on #ffffff   4.48:1  AA FAIL  AAA FAIL
4 checked, 3 passed AA, 1 failed AA
```

The two skipped rules are reported on standard error, not in the
report:

```text
skipped .no-bg (colour set, no background)
skipped .named (colour is not hex)
```

The command exits 1, because `.faint` fails AA. A file with no
failing pair exits 0.

Check a list of pairs:

```sh
python3 src/colour_contrast_checker.py --pairs examples/pairs.txt
```

Real output:

```text
PASS  black on white                #000000 on #ffffff  21.00:1  AA PASS  AAA PASS
PASS  dark grey on white            #333333 on #ffffff  12.63:1  AA PASS  AAA PASS
PASS  grey text                     #767676 on #ffffff   4.54:1  AA PASS  AAA FAIL
FAIL  faint grey text               #777777 on #ffffff   4.48:1  AA FAIL  AAA FAIL
FAIL  white on white                #ffffff on #ffffff   1.00:1  AA FAIL  AAA FAIL
5 checked, 3 passed AA, 2 failed AA
```

Check two colours directly:

```sh
python3 src/colour_contrast_checker.py "#000000" "#ffffff"
```

```text
PASS  command line                  #000000 on #ffffff  21.00:1  AA PASS  AAA PASS
1 checked, 1 passed AA, 0 failed AA
```

## Examples

### 1. Fail CI on an AA fail

```sh
python3 src/colour_contrast_checker.py examples/sample.css
echo $?
```

```text
1
```

The exit code is 1 because `.faint` (#777777 on #ffffff, 4.48:1)
is below the AA 4.5:1 line. Put the same command in CI and the
build fails until the colour is fixed.

### 2. Large text has lower limits

`#777777` on white fails AA for normal text, but passes AA for
large text (3:1):

```sh
python3 src/colour_contrast_checker.py "#777777" "#ffffff" --large
```

```text
PASS  command line                  #777777 on #ffffff   4.48:1  AA PASS  AAA FAIL
1 checked, 1 passed AA, 0 failed AA
```

### 3. Require AAA

`#767676` on white passes AA (4.54:1) but not AAA (7:1):

```sh
python3 src/colour_contrast_checker.py "#767676" "#ffffff" --level aaa
```

```text
PASS  command line                  #767676 on #ffffff   4.54:1  AA PASS  AAA FAIL
1 checked, 0 passed AAA, 1 failed AAA
```

The exit code is 1. The `PASS` in the first column is the AA
verdict; the `--level aaa` summary and exit code are the ones that
count.

## How it is tested

```sh
python3 tests/test_colour_contrast_checker.py
```

34 tests, standard library `unittest` only — no third-party
packages. They cover: the WCAG ratio math (black on white is
21.00:1, same colour is 1.00:1), the AA/AAA limits for normal and
large text, the two edge greys (#767676 passes AA at 4.54:1,
#777777 fails AA at 4.48:1), hex parsing (3-digit, 6-digit, bad
values), CSS parsing (both colours, missing background, named
colours, comments, shorthand background), pairs files, the CLI
end-to-end (pass exits 0, fail exits 1, bad input exits 2), and a
check that the code and the tests import standard library only.

The bundled example is a real run, not made-up output:

```sh
sh examples/run-example.sh
```

It checks `examples/sample.css` and `examples/pairs.txt` and
prints the real output. The committed
`examples/sample-output.txt` is the output of the sample CSS run.

## Contributing

Small, focused improvements are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

Built from scratch for this repo. The WCAG contrast ratio is the
standard formula from the WCAG 2.1 guidelines (relative luminance
and the (L1 + 0.05) / (L2 + 0.05) ratio); no code was copied from
any existing checker.
