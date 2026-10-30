# The board's page

This file belongs to the `update-build-board` skill. It says what the page is made of, how to change the page or the generator, and how to verify a change by running the page. `SKILL.md` beside it names the setup every board runs, each repository's pin and inputs, and where the page lives.

## What the page is made of

A heading, a strip and three sections, top to bottom. The heading and the browser tab show `STATE.title`. Under the heading sits a subtitle, which is `STATE.subtitle` under the `subtitle` input and the page's own "what is in flight, and what to take next" otherwise. The strip renders two `STATE` figures: the open issue count, and the stamp drawn from `updatedAt`. Under the strip sits the caller's paragraph, `STATE.note`, under the `note` input, and nothing otherwise.

Keep the strip to figures that say what to take next. l3a0/quantitative-trading's strip used to carry five more, and the owner removed all five on 2026-10-05 UTC.

1. The commit `main` stood at.
2. The vintage files and their rows.
3. The committed highlights.
4. The suite's test count.
5. The experiments tracked.

The test count alone cost a full suite run per update, 532 seconds on `ec44e94`, and a merge during that run made the count describe a commit that was no longer `main`, so the run had to start over. That happened the day they were removed, when [l3a0/quantitative-trading PR #363](https://github.com/l3a0/quantitative-trading/pull/363) merged mid-run. None of the five said what to take next, which is the question the page answers, so do not add them back. Under the `default-branch-head` input the footer names the commit the default branch stood at instead, from `STATE.main`, and so does the banner that says live updates stopped.

The sections are these.

1. **In flight**, five columns running most finished on the left: waiting on your review, waiting on my review, building, planned with no builder, and being planned. A card here is drawn once and left out of the build order. Two of the five hold a card only because a session is on it, and the kind of `working:` label is what separates a build session from a decompose loop. A third, waiting on my review, also holds a card whose branch is open and whose session has not handed it over.
2. **Build order**, columns by how many steps along a chain of open blockers a card sits. The page draws three, and a fourth, "Waiting on data", for cards whose `kind` is `data`, whenever the tracker holds one. Only a caller naming a data label gets such a card. By default the columns hold the ranked cards, and with Show all they hold everything not in flight. Within a column, cards sort by readiness, then by the priority order, then by a measured `after`, then by number, except that a card whose `kind` is `deferred` is forced last whatever the rest says. Under it sits a chain bar, which holds a hint until a card is picked and then says what that card waits on and what waits on it.

   By default the section draws only the cards `NEXT` ranks, and a line above the columns counts the rest and carries a **Show all** button. With every open issue drawn on l3a0/quantitative-trading's board, the first column ran past fifty cards and the ten ranked ones were scattered through it. The Marketlake Build Board made the same cut at a hundred and fifty. The choice is kept in the viewer's browser and nowhere else, under `board-all:<owner/repo>`. Every board an owner publishes is served from the one origin `<owner>.github.io`, so a key shared by all of them would let one board's toggle flip another's. A card whose `kind` is `deferred` stays hidden even when it carries a band, because `rankMark` drops it. A band of 5 does not hide a card on its own. So under the band rule a card in the build-order columns shows by default exactly when it carries a `band:N` label and its `kind` is not `deferred`. A card in flight shows either way. A band label is how a card gets onto the short view, and that view is what the owner reads first. Under `ranking: order` an order line does the band's job, per milestone, as moment 7 in `SKILL.md` says. There a milestone in which nothing is ranked draws every card instead, because the ranked-only view would draw nothing, and the line above the columns says nothing is ranked.
3. **One paragraph**, saying how the board is built and that every figure on it dates from the stamp. It is all that remains of the twenty-paragraph footer l3a0/quantitative-trading's page once carried, which was a second telling of what the cards say. Do not grow it back.

Between the strip and the first section sits a banner. Over a current board it is empty. It warns when the stamp is older than `staleAfterMinutes`, because a failed run leaves the last board up and a board hours stale looks like a fresh one. It also speaks when the page has no board to show, or has stopped taking fresh copies, and says which and how old any data on screen is. With no board data the page hides both sections and the footer and draws only the banner, so a missing or unreadable `board.json` never reads as an empty board.

Under the `milestone-default` input the page also draws a milestone selector under the strip. It lists "All" and each milestone the open cards carry, by the short name `SKILL.md`'s data section gives, with a count beside each. It opens on `STATE.milestoneDefault`, or on All when that is null. The reader's choice is kept in the browser under `board-ms:<owner/repo>`, for the same reason as the Show all choice. The page falls back to the default whenever the stored choice names a milestone no open card carries, without forgetting it, so the choice comes back if a card returns to that milestone. The selector decides only what is drawn. The column a card sits in, its blockers, the In flight split, the strip and the footer still read the whole board, so a card keeps its "waits on" line when its blocker sits in another milestone. Under one milestone a parent in it shows beside the ranked cards, because a parent is never ranked and its children name it as what they serve.

### The page's constants

The page's constants live in its code rather than in the data.

| Constant | Holds |
| --- | --- |
| `FLOW` | the five in-flight stages and the test that assigns a card to one |
| `LABEL_HUE` | one colour per label, used as the chip's ink: the kind and work labels the template creates, `bug`, `documentation`, `enhancement`, `test`, `deferred`, `question` and `decision`, and `blocked-on-data`, the example data label. Any other label renders in the faint ink until a code change adds its colour. Under the `label-colors` input every chip is instead filled with the colour GitHub stores for its label, from `STATE.labelColors`, and lettered in black or white, whichever contrasts more. A label recoloured on GitHub shows at the board's next run, because editing a label starts none |
| `COLS` | the build-order column headings and their subtitles, which are rendered prose. The page holds four, and draws the fourth only when the tracker holds a `data` card |
| `KINDWORD` | the phrase a card prints for its `kind`, such as "deferred on purpose". A new kind prints no phrase until a code change adds one |
| `READY_RANK` | the order `build`, `decide` and `plan` sort in, read by the ranking sort |

## Change the page or the generator

Change the page only when the rendering has to change. A change to the page, the stub, the template's icon or the generator happens in l3a0/repo-template, never in a seeded repository, because a seeded repository runs the template's copies at its pin and any local copy would run nowhere. Edit the file in the template, run its `tests/test_build_board.py` and `tests/test_build_board_generator.py` and the harness below, and open the pull request there. The board run that the merge starts publishes the template's own board from `main`. A seeded repository picks the change up by moving its pin: edit the ref on the `uses:` line in its `.github/workflows/board.yml` to the template commit that carries the change. The skills and the generator share the label names, the line formats and the list of changes that start no run, so a pin moved past a format change also needs the plugin release that `SKILL.md`'s `## Generator compatibility` describes. Each repository's copy of the two skills once moved with its pin in the same pull request. The plugin replaced those copies, and the compatibility table is what records which generator commits the plugin's copy matches.

The page links its tab icon as `favicon.ico`, and the reusable workflow copies the template's `favicon.ico` from beside the page into the same folder, unless the caller names its own. Renaming the icon means changing the page's link, that copy and the tests that check them together.

A seeded repository's own icon is the one exception, because it is the repository's mark rather than the board's rendering. The repository commits an `.ico` file and names it in its caller's job with `with: icon: <path>`, such as `.github/board/favicon.ico`. The reusable workflow then serves that file as `favicon.ico` in the template's place, and a path that names no file fails the run, so the last board stays up. Naming the file needs a pin at or after the template commit that added the `icon` input, `9c6d7e2`, because a caller passing an input the called workflow does not declare fails. After that, changing the icon means changing the file, with no move of the pin.

A seeded repository whose issues can wait on data that has to be bought or captured names the label it marks them with in the same job, as `with: data-label: <label>`. Its cards then take the kind `data` and draw in the fourth column. Naming it needs a pin at or after the template commit that closes [l3a0/repo-template#40](https://github.com/l3a0/repo-template/issues/40), `26e5010`, for the same reason.

Three inputs set lines the repository's own page used to carry. A caller names them in the same job, written here one to a line: `with: subtitle: ` followed by the line under the heading, `with: note: ` followed by the paragraph under the strip, and `with: default-branch-head: "true"`. The note is plain text whose only markup is `[words](https://...)`, and a link to anything but an `https://` address fails the run. Use YAML's folded form, `note: >-`, for a long one, since runs of whitespace read as one space.

Two inputs change the label chips. `with: label-colors: "true"` fills each chip with the colour GitHub stores for its label, and `with: sort-labels: "true"` sorts each card's labels by name rather than in the order they were added.

`with: milestone-default: MVP <n>` draws the milestone selector, opening on the lowest-numbered milestone the open cards carry whose name up to its first comma reads `MVP` and a number. A name with no `<n>` names one milestone exactly. The reader's choice is kept under `board-ms:<owner/repo>`, as the section above says.

Each of these six needs a pin at or after the commit that first declared it, which `SKILL.md`'s `## Generator compatibility` lists with the pin to use.

A change to what the page reads is a change to the generator as well, in the same pull request, because the workflow builds `board.json` and copies the page in the same run. Add the field to the generator, and to `ITEM_OK` in the page if the renderer reads it without a guard, because the page refuses a whole section when one item lacks a field it reads. A change to what the generator reads from GitHub, or a new input, is a format change, so it needs the plugin release `SKILL.md` describes.

## Verify by executing, never by reading

A parse check is not enough, because a comma dropped inside a nested array still parses. l3a0/repo-template's tests run the page against invented fixtures, which catches a page that throws, draws a section from the wrong document, or mislabels an empty board. They cannot read live data, so running the page on a board built from GitHub is still the check on what a viewer will see.

### The harness

`tests/test_build_board.py` in l3a0/repo-template runs the page against invented fixtures. The harness runs the page's script under `osascript`, which has no fetch, so it hands the page a fake one serving a `board.json` built as `SKILL.md`'s `## Where the board lives` says. First put the page and the stub beside that `board.json`. From the repository root, after the setup block in `SKILL.md`:

```bash
template .claude/skills/update-build-board/board.html > <scratch>/board.html &&
template .claude/skills/update-build-board/dom-stub.js > <scratch>/dom-stub.js
```

In l3a0/repo-template, when the change under test is the page itself, copy the two files from the working tree instead, because the change is on no pinned ref yet. Then run this from the scratch directory.

```bash
python3 -c "
import json,re,sys
t=open(sys.argv[1]).read()
open('board.js','w').write(re.search(r'<script>(.*?)</script>', t, re.S).group(1))
open('serve.js','w').write('var fetch=function(){return Promise.resolve({ok:true,status:200,'
  'text:function(){return Promise.resolve('+json.dumps(open('board.json').read())+');}});};\n')
" board.html
cat > print.js <<'JS'
(async function(){ for (var i=0;i<50;i++) { await null; }
function s(x){return String(x).replace(/<[^>]+>/g," ").replace(/\s+/g," ").trim();}
var o=[];
o.push("STRIP: "+s(store.strip.innerHTML));
store.flow.innerHTML.split('<div class="col f-').slice(1).forEach(function(c){
  var h=c.match(/<span class="t">([^<]+)<\/span><span class="c">(\d+)<\/span>/);
  var ids=(c.match(/data-n="(\d+)"/g)||[]).map(function(m){return "#"+m.match(/\d+/)[0];});
  var d=c.match(/<span class="d">([^<]*)<\/span>/);
  o.push("flow  "+h[1]+"="+h[2]+": "+(ids.join(" ")||"(empty)"));
  o.push("  sub "+(d?d[1]:"(none)"));
  var wk=(c.match(/<div class="wk">[^<]*<\/div>/g)||[]).map(s);
  o.push("  wk  "+(wk.join(" | ")||"(none)"));});
store.board.innerHTML.split('<div class="col k').slice(1).forEach(function(c){
  var h=c.match(/<span class="t">([^<]+)<\/span><span class="c">(\d+)<\/span>/);
  var ids=(c.match(/data-n="(\d+)"/g)||[]).map(function(m){return "#"+m.match(/\d+/)[0];});
  var d=c.match(/<span class="d">([^<]*)<\/span>/);
  o.push("board "+h[1]+"="+h[2]+": "+ids.join(" "));
  o.push("  sub "+(d?d[1]:"(none)"));
  var wk=(c.match(/<div class="wk">[^<]*<\/div>/g)||[]).map(s);
  o.push("  wk  "+(wk.join(" | ")||"(none)"));});
o.push("FLOWNOTE: "+s(store.flownote.innerHTML));
o.push("BOARDNOTE: "+s(store.boardnote.innerHTML));
o.push("KEY: "+s(store.key.innerHTML));
o.push("FLOWKEY: "+s(store.flowkey.innerHTML));
store.foot.innerHTML.split("<p>").slice(1).forEach(function(x,i){
  o.push("FOOT["+(i+1)+"] "+s(x));});
// Anything the page wrote to that the lines above do not format. Listing the
// surfaces by hand is what let `chainbar` go unread and a dead `rank` probe go
// unnoticed, so the sweep is what keeps that list honest. It sees load-time
// `innerHTML` only: not `stamp`, which only a timer writes, not any
// `aria-label`, since the tag-stripper deletes attributes, and not the
// chain bar's picked state, which needs a click. It cannot see code that
// renders nothing either, which is defect 13 and wants a grep rather than a read.
var shown = {strip:1, flow:1, board:1, flownote:1, boardnote:1, key:1, flowkey:1, foot:1};
Object.keys(store).sort().forEach(function(id){
  if (!shown[id]) o.push("OTHER["+id+"] "+s(store[id].innerHTML));});
console.log(o.join("\n")); })();
JS
cat dom-stub.js serve.js board.js print.js > run.js
osascript -l JavaScript run.js
```

The page fetches on load and draws once the answer arrives, which is after the script's last line, so the printing waits for it rather than running at once.

That run draws the default view, which hides every card `NEXT` does not rank. Under `ranking: order` a milestone in which nothing is ranked is the exception, and draws every card. Under `milestone-default` the default view also draws only the default milestone. Run it a second time with the Show all view and every milestone, because most of the columns and most of the board note only render there. The stub has no `localStorage`, so one line before the script supplies the stored choices. It answers "1" for a key starting `board-all:`, `,all` for a key starting `board-ms:`, which is the value of the selector's All entry, and nothing for any other key. So a page reading a renamed key draws the short view and the run shows it.

```bash
(cat dom-stub.js serve.js
 echo 'var localStorage={getItem:function(k){k=String(k);return k.indexOf("board-all:")===0?"1":k.indexOf("board-ms:")===0?",all":null;},setItem:function(){}};'
 cat board.js print.js) > run-all.js
osascript -l JavaScript run-all.js
```

`osascript -l JavaScript` is JavaScriptCore, and it is what runs this where no `node` is installed. It is macOS only. Anywhere else, run the same files with whatever JavaScript engine is present, because the stub is plain ES5 and assumes nothing about its host.

**Print every surface the page renders into, not only the interesting ones.** A harness that skips a surface cannot see a defect on it, and three gaps of this kind have each hidden one on l3a0/quantitative-trading's page.

1. **The footer, the key and the flow key.** An earlier version of the harness skipped `foot`, `key` and `flowkey`, and `foot` is the largest prose block on the page and the one holding the most hand-written numbers. Planting a false figure in it left the output byte-identical, so the check could not see the surface it was most needed on.
2. **The column subtitles.** The harness printed each column's title and count and skipped the subtitle under them, so a change rewriting the "Waiting on" subtitles for defect 17 could have been reverted without the output moving. Each column now prints a `sub` line under it.
3. **The session phrase under a card.** On 2026-10-05 the page stopped drawing a card's `what` phrase under "Building" and "Being planned", and the harness printed the same output for that page and for one with the change reverted, because it printed no card's lines at all. Each column now prints a `wk` line listing the session phrases its cards drew, and `(none)` where they drew none. Later the same day the page stopped drawing the phrase under "Waiting on my review" as well, so every `wk` line now reads `(none)`, and a phrase showing up on any of them is the line coming back.

**Much of the page is dark when no branch is open and no session holds a card**, which is the state it is in between batches. The flow note collapses to a sentence, the flow legend loses two entries, and the footer's decay clause disappears entirely. That clause is where check 5's conjunction lives, so on an empty board the sentence it warns about cannot be read at all. Where a change touches that code, add a `prs` or `working` entry to a scratch copy of `board.json`, rebuild `serve.js` from it, run the harness and read the output.

### A live run in a browser

The tests and the harness feed documents someone thought of. To see the changed page draw the board as GitHub stands, build `board.json` from live data with the build command in `SKILL.md`, using `<scratch>/site` as its scratch directory, and serve the page beside it, laid out as the workflow lays them out. In l3a0/repo-template, copy the page under test from the working tree rather than fetching it.

```bash
template .claude/skills/update-build-board/board.html > <scratch>/site/index.html
template .claude/skills/update-build-board/favicon.ico > <scratch>/site/favicon.ico
uv run --no-project --python '>=3.12' python -m http.server 8799 --bind 127.0.0.1 --directory <scratch>/site
```

Run the server in the background, open <http://127.0.0.1:8799/> in a browser, and read the page under its default milestone and under "All", where the board has a selector. Serve the page at the caller's pin beside the same `board.json` and compare the two. Every difference should be one the change intends. Stop the server when done.

### Read the output rather than checking that it ran

About half the defects l3a0/quantitative-trading's page shipped were sentences that rendered perfectly and said something false. Six checks catch most of them.

1. **The totals reconcile.** In-flight cards plus board cards plus the hidden count on the `OTHER[more]` line equals open issues, and every card carries its labels. In the Show all run nothing is hidden, so the number on that run's `OTHER[more]` line must equal the board cards, and in-flight plus board cards alone must equal open issues.
2. **No sentence contradicts another.** The free-card list must not name a card that a later sentence says nobody should start.
3. **Every count matches its own list.** A sentence saying four cards and then naming three is the prose and the data disagreeing.
4. **No figure is typed into a sentence.** Every number the page renders should come from the data, so that changing the data changes the page. This holds today and did not always: the footer used to carry twenty paragraphs of hand-written prose, and one update left four stale figures in it at once. Deleting that prose is what made this check cheap, so the thing to watch for is prose growing back rather than a surface to re-read.
5. **Every joined sentence says what it means.** A computed sentence joins clauses that each drop out on their own, so a "too" or an "and" can outlive the clause it referred back to. One read "#27 is planned too" with nothing before it, because the card it was agreeing with had merged. A conjunction can also be present and be the wrong word: a set of alternatives joined by "and" reads as one card doing all of them at once. So read what a joined sentence claims rather than only checking that both halves are there, and read the sentences rather than only the counts.
6. **Nothing a card says contradicts where the card sits.** A marker, a line of text and a position are three claims about one issue, and a rule added to any of them can disagree with the other two. A chip once read 6 on a card the sort had forced to the bottom. Read each card's own marks against its place in the column.

One class the six cannot reach. Every check above reads what the page rendered, so none of them sees code that renders nothing. Defect 13 in [record.md](record.md) is that class, and what catches it is a grep rather than a read.

## Writing the prose

The repository's own writing rules govern the page's prose. Impersonal voice, no first person, no em dashes or semicolons, short complete sentences, a counted set written as a list rather than inlined, and the price of a choice named rather than hidden.

One exception is deliberate and load-bearing. The in-flight column headings say "Waiting on my review" and "Waiting on your review", and the whole point of those two columns is whose move it is. "My" is the session's and "your" is the owner's. Applying the impersonal rule to them deletes the distinction the section exists to draw. Keep the first and second person there, and nowhere else.

Two further conventions are specific to this page.

1. **Say what the page cannot know.** The in-flight section is the most perishable thing on it, because a session ends without telling anyone and a review posted a minute after the stamp still reads as owed. The footer says so, and it keeps saying so.
2. **A comment explains why a rule exists, not what the line does.** The generator's comments carry the measurements behind its choices, which is what stops the next session undoing one by accident.

## Which copy wins where this skill and the page overlap

Several things are reasoned about twice, once in a comment beside the line it governs and once in this skill. The duplication is deliberate and its price is named rather than hidden, because nothing checks the two against each other.

The split is by question. A comment in the page or the generator answers why that line is the way it is, and it is authoritative about the code it sits on, because it travels with the code through any rewrite. This skill answers how to run an update and what has gone wrong before, and it is authoritative about the procedure and the record.

So when the two disagree about a mechanism, the comment is right and this skill is what gets corrected, through a plugin release. When they disagree about what a session should do, this skill is right. A session changing the page's behaviour updates the comment on the line it edits, and checks this skill for a sentence describing the same mechanism.
