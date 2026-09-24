from __future__ import annotations

import html
import shutil
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from welcome.mailer import Mailer, RecordingMailer
from welcome.models import HIRED, Hire, now, stamp
from welcome.monitor import check
from welcome.render import TemplateError, render
from welcome.runner import run
from welcome.sent_log import SentLog
from welcome.source import CsvSource, SchemaError
from welcome.validate import problems

HERE = Path(__file__).resolve().parent.parent
DEMO = HERE / "demo"
TEMPLATE = HERE / "templates" / "welcome.txt"


@dataclass
class App:
    csv: Path = DEMO / "hires.csv"
    log_path: Path = DEMO / "sent.jsonl"
    template: Path = TEMPLATE
    mailer: Mailer = field(default_factory=RecordingMailer)

    @property
    def source(self) -> CsvSource:
        return CsvSource(self.csv)

    @property
    def log(self) -> SentLog:
        return SentLog(self.log_path)

    def add_hire(self, form: dict[str, list[str]]) -> str:
        source = self.source
        hire = Hire(
            hire_id=source.next_id(),
            name=(form.get("name") or [""])[0].strip(),
            email=(form.get("email") or [""])[0].strip(),
            status=HIRED,
            hired_at=stamp(now()),
            start_date=(form.get("start_date") or [""])[0].strip(),
        )
        found = problems(hire)
        if found:
            return "Not added: " + "; ".join(found)
        source.add(hire)
        return f"{hire.name} added as {hire.hire_id}. The next pass will write to them."

    def run_pass(self, dry_run: bool) -> str:
        report = run(self.source, self.mailer, self.log, str(self.template), dry_run=dry_run)
        if dry_run:
            if not report.would_send:
                return "Nothing to send. " + report.line()
            listed = ", ".join(f"{email} ({hire_id})" for hire_id, email, _ in report.would_send)
            return f"Would send to {listed}. Nothing was written."
        return report.line()

    def letter(self, hire_id: str) -> tuple[str, str]:
        hire = next((h for h in self.source.rows() if h.hire_id == hire_id), None)
        if hire is None:
            return "Unknown hire", f"No row with id {hire_id}."
        try:
            return render(self.template, hire)
        except (TemplateError, OSError) as exc:
            return "This letter cannot be built", str(exc)


PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New therapist welcome</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font: 15px/1.5 system-ui, sans-serif; color: #17202a; background: #f6f7f9;
         margin: 0; padding: 24px 16px 64px; }}
  main {{ max-width: 920px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  p.lede {{ color: #5b6673; margin: 0 0 24px; }}
  section {{ background: #fff; border: 1px solid #e2e6eb; border-radius: 8px;
             padding: 16px 18px; margin-bottom: 18px; }}
  h2 {{ font-size: 15px; margin: 0 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eef1f4;
            vertical-align: top; }}
  th {{ font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #6b7684; }}
  td.note {{ color: #8a5200; font-size: 13px; max-width: 260px; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
  .Hired {{ background: #e7f0fe; color: #12467b; }}
  .Sent {{ background: #e6f5ec; color: #17603a; }}
  .Sending {{ background: #fdf1dc; color: #7a4b00; }}
  .Needs {{ background: #fde8e8; color: #8b1d1d; }}
  .Interviewing {{ background: #eef1f4; color: #55606d; }}
  form.row {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; }}
  label {{ display: block; font-size: 12px; color: #6b7684; margin-bottom: 4px; }}
  input {{ font: inherit; padding: 7px 9px; border: 1px solid #ccd3da; border-radius: 6px;
           background: #fff; }}
  button {{ font: inherit; padding: 8px 14px; border-radius: 6px; border: 1px solid #ccd3da;
            background: #fff; cursor: pointer; }}
  button.go {{ background: #17202a; border-color: #17202a; color: #fff; }}
  .msg {{ background: #eef4ff; border: 1px solid #ccdcfb; border-radius: 6px;
          padding: 10px 12px; margin-bottom: 18px; }}
  .page, .warn {{ font-size: 13px; padding: 2px 0; }}
  .page::before {{ content: "alert "; color: #8b1d1d; font-weight: 600; }}
  .warn::before {{ content: "check "; color: #7a4b00; font-weight: 600; }}
  .quiet {{ color: #6b7684; font-size: 13px; }}
  a {{ color: #12467b; }}
</style>
<main>
  <h1>New therapist welcome</h1>
  <p class="lede">A hire added here gets one welcome email, sent by the job that runs
  every ten minutes. Nothing on this page sends twice.</p>
  {message}
  <section>
    <h2>Add a hire</h2>
    <form class="row" method="post" action="/hires">
      <div><label for="name">Name</label><input id="name" name="name" required></div>
      <div><label for="email">Email</label><input id="email" name="email" type="email" size="28" required></div>
      <div><label for="start_date">First day</label><input id="start_date" name="start_date" placeholder="2026-10-05" required></div>
      <button class="go" type="submit">Add</button>
    </form>
  </section>
  <section>
    <h2>Hires</h2>
    <table>
      <tr><th>Id</th><th>Name</th><th>Email</th><th>Status</th><th>First day</th><th>Welcomed</th><th>Note</th></tr>
      {rows}
    </table>
    <form class="row" method="post" action="/run" style="margin-top:16px">
      <button name="dry" value="1" type="submit">Preview what would go out</button>
      <button class="go" type="submit">Send now</button>
    </form>
  </section>
  <section>
    <h2>Monitor</h2>
    {alerts}
  </section>
</main>
</html>
"""

LETTER = """<!doctype html>
<html lang="en"><meta charset="utf-8"><title>{subject}</title>
<style>body {{ font: 15px/1.6 system-ui, sans-serif; max-width: 640px; margin: 40px auto;
 padding: 0 16px; color: #17202a; }}
 pre {{ white-space: pre-wrap; background: #f6f7f9; border: 1px solid #e2e6eb;
 border-radius: 8px; padding: 16px; font: inherit; }}
 a {{ color: #12467b; }}</style>
<p><a href="/">back</a></p><h1>{subject}</h1><pre>{body}</pre></html>
"""


def render_page(app: App, message: str = "") -> str:
    rows = app.source.rows()
    alerts = check(rows, app.log)
    return PAGE.format(
        message=f'<p class="msg">{html.escape(message)}</p>' if message else "",
        rows="\n      ".join(_row(hire) for hire in rows)
        or '<tr><td colspan="7" class="quiet">No hires yet.</td></tr>',
        alerts="\n    ".join(
            f'<p class="{"page" if a.level == "page" else "warn"}">{html.escape(a.text)}</p>'
            for a in alerts
        )
        or '<p class="quiet">Nothing waiting, nothing held.</p>',
    )


def _row(hire: Hire) -> str:
    e = html.escape
    welcomed = (
        f'{e(hire.welcome_sent_at)}<br><span class="quiet">{e(hire.welcome_message_id)}</span>'
        if hire.welcomed
        else '<span class="quiet">not yet</span>'
    )
    return (
        f"<tr><td>{e(hire.hire_id)}</td>"
        f'<td><a href="/letter?hire={quote(hire.hire_id)}">{e(hire.name)}</a></td>'
        f"<td>{e(hire.email)}</td>"
        f'<td><span class="tag {_tag(hire.status)}">{e(hire.status)}</span></td>'
        f"<td>{e(hire.start_date)}</td><td>{welcomed}</td>"
        f'<td class="note">{e(hire.note)}</td></tr>'
    )


def _tag(status: str) -> str:
    first = status.split()[0] if status.split() else "Interviewing"
    return html.escape(first if first.isalpha() else "Interviewing")


def handler_for(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "welcome/0.1"

        def do_GET(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/":
                self._html(render_page(app, (query.get("msg") or [""])[0]))
            elif url.path == "/letter":
                subject, body = app.letter((query.get("hire") or [""])[0])
                self._html(LETTER.format(subject=html.escape(subject), body=html.escape(body)))
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            try:
                if self.path == "/hires":
                    message = app.add_hire(form)
                elif self.path == "/run":
                    message = app.run_pass(dry_run=bool(form.get("dry")))
                else:
                    return self.send_error(404)
            except SchemaError as exc:
                message = f"The tracker is missing a column this job writes to: {exc}"
            self.send_response(303)
            self.send_header("Location", f"/?msg={quote(message)}")
            self.end_headers()

        def _html(self, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def demo_tracker() -> None:
    if not (DEMO / "hires.csv").exists():
        DEMO.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE / "sample" / "hires.csv", DEMO / "hires.csv")


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    demo_tracker()
    server = ThreadingHTTPServer((host, port), handler_for(App()))
    print(f"the hiring page is at http://{host}:{port}  (ctrl+c to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
