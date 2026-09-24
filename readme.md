# The welcome email, automated

The exercise: every new therapist gets a welcome email by hand, and hiring is tracked in
a spreadsheet several people edit. This is that automation as something running rather
than a diagram, because the interesting part is not the sending. It is what happens when
the sheet is edited under the job, when the send half finishes, and when the whole thing
quietly stops.

Python 3.12, standard library only, including the page. Nothing to install.

```
python3 -m welcome
```

Then open http://127.0.0.1:8000. It builds a sandbox tracker with five hires on first
start, and nothing it does leaves the machine: the mailer records instead of sending.
Delete `demo/` to start over.

## What the page does

Add a hire, and the row is the record. A name links to the letter that person would get,
rendered from their row, so it can be read before it goes. **Preview** shows what would
be sent and writes nothing. **Send now** is the pass a schedule would run every ten
minutes, so pressing it twice still sends one email each. The block at the bottom is the
monitor.

## What happens on a hire

1. Check the tracker still has the columns the job writes to.
2. Skip anyone already in the send log.
3. Validate the row. A bad address goes to `Needs review` with the reason, not to silence.
4. Claim the row with a compare and set, so two runs cannot both take it.
5. Render the template and send, through the Google Workspace API in production.
6. Write the send log first, then the row. That order is deliberate: a crash between them
   leaves a row that looks unsent next to a log that says sent, and that is repairable.
   The other order sends twice.

## What could go wrong

| What happens | What it does |
|---|---|
| The job runs twice, or two copies overlap | The claim decides. The loser skips the row |
| Someone clears the "sent" column by pasting | The send log, not the sheet, decides. The row is repaired, not re-sent |
| The host dies mid send | Repaired from the log, or released back to `Hired` after 30 minutes |
| A typo in an email | `Needs review` with the reason, so it becomes work for a person |
| A renamed column | The run fails loudly. It does not skip every row and report success |
| A rate limit or a full mailbox | Retried with a widening pause, three times, then held |
| PHI in a letter | The template can only see name, first name, start date and hire id |

## How you would know it stopped

A job that silently does nothing looks exactly like a quiet hiring week.

1. **A dead man's switch.** On a schedule, every finished pass pings healthchecks.io and
   the alert comes from the absence of a ping, so it still fires when the box is off, the
   token expired or the schedule was disabled. Nothing inside the job can suppress it.
2. **The work, not the job.** Rows sitting in `Hired` for over an hour with no message
   id, rows stuck mid send, rows in `Needs review`. The job can run happily every ten
   minutes and still send nothing, and this is what sees that.
3. **A weekly count.** New hires against sends, ending a day short of now so work in
   flight is not counted as a miss.

A sheet does not remember when a cell changed, so whoever sets the status writes
`hired_at` beside it. Without that a row can be called unsent but never late, and the
monitor says so instead of guessing.

## In production

The demo runs on a CSV and a mailer that records. A Google Sheet or Airtable is the same
five methods in `source.py`, and the Gmail API is the same one method in `mailer.py`.
Roughly a day to build against a real sheet and mailbox, including a week of dry runs
with a person reading each letter.

```
welcome/models.py     the row, the statuses, time in one format
welcome/source.py     the tracker behind five methods
welcome/mailer.py     send() returning a message id
welcome/sent_log.py   append only, one line per hire, the reason nobody gets two
welcome/validate.py   what has to be true before anything is sent
welcome/render.py     the letter, editable by people who do not write code
welcome/runner.py     one pass: claim, send, log, write back, repair
welcome/monitor.py    the three signals
welcome/web.py        the page
```
