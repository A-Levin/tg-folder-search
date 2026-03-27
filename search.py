#!/usr/bin/env python3
import asyncio
import argparse
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import DialogFilter

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static
from textual.binding import Binding
from textual.screen import Screen

import db as database

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.path.expanduser("~/.tg-folder-search-session")

STATUS_ICON = {
    "favorite": "[yellow]★[/yellow]",
    "seen": "[dim]✓[/dim]",
    "skipped": "[dim]✗[/dim]",
    "new": " ",
}


@dataclass
class Vacancy:
    channel: str
    date: str
    title: str
    salary: Optional[str]
    location: Optional[str]
    stack: Optional[str]
    link: str
    full_text: str
    status: str = "new"


def extract_info(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    title = re.sub(r"[\*_`#]+", "", lines[0]).strip() if lines else "—"

    salary, location, stack = None, None, None
    for line in lines[1:]:
        cl = line.lower()
        if not salary and re.search(r"зарплат|зп\b|вилка|salary|\$\s*\d|€\s*\d|от \d", cl):
            salary = re.sub(r"^[^:：]+[:：]\s*", "", line).strip() or line
        if not location and re.search(r"локаци|location|формат|город|офис|remote|удален", cl):
            location = re.sub(r"^[^:：]+[:：]\s*", "", line).strip() or line
        if not stack and re.search(r"стек|stack|технолог|требовани|навык|скилл|skill", cl):
            stack = re.sub(r"^[^:：]+[:：]\s*", "", line).strip() or line

    return title, salary, location, stack


def make_link(entity, msg_id: int) -> str:
    if getattr(entity, "username", None):
        return f"https://t.me/{entity.username}/{msg_id}"
    cid = str(getattr(entity, "id", "")).lstrip("-")
    if cid.startswith("100"):
        cid = cid[3:]
    return f"https://t.me/c/{cid}/{msg_id}" if cid else ""


def title_str(f) -> str:
    t = f.title
    return t.text if hasattr(t, "text") else str(t)


async def fetch_results(query: str, folder_title: str, limit: int, days: Optional[int]) -> list[Vacancy]:
    vacancies = []
    offset_date = datetime.now(timezone.utc) - timedelta(days=days) if days else None

    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        filters = await client(GetDialogFiltersRequest())
        folder = next(
            (f for f in filters.filters if isinstance(f, DialogFilter) and title_str(f) == folder_title),
            None,
        )
        if not folder:
            available = [title_str(f) for f in filters.filters if isinstance(f, DialogFilter)]
            print(f"Папка «{folder_title}» не найдена. Доступные: {', '.join(available)}")
            return vacancies

        for peer in folder.include_peers:
            try:
                entity = await client.get_entity(peer)
                async for msg in client.iter_messages(entity, search=query, limit=limit, offset_date=offset_date):
                    text = msg.text or msg.message or ""
                    if not text:
                        continue
                    title, salary, location, stack = extract_info(text)
                    vacancies.append(Vacancy(
                        channel=getattr(entity, "title", "?"),
                        date=msg.date.strftime("%d.%m.%Y"),
                        title=title,
                        salary=salary,
                        location=location,
                        stack=stack,
                        link=make_link(entity, msg.id),
                        full_text=text,
                    ))
            except Exception:
                continue

    statuses = database.get_all_statuses()
    for v in vacancies:
        v.status = statuses.get(v.link, "new")

    vacancies.sort(key=lambda v: v.date, reverse=True)
    return vacancies


async def fetch_favorites() -> list[Vacancy]:
    favs = database.get_favorites()
    if not favs:
        return []
    links = {f["link"] for f in favs}
    print(f"В избранном {len(links)} вакансий (ссылки сохранены локально).")
    return []


class DetailScreen(Screen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Назад")]

    def __init__(self, vacancy: Vacancy):
        super().__init__()
        self.vacancy = vacancy

    def compose(self) -> ComposeResult:
        v = self.vacancy
        yield Header()
        text = (
            f"[bold]{v.title}[/bold]\n\n"
            f"[dim]Канал:[/dim] {v.channel}   [dim]Дата:[/dim] {v.date}\n"
            + (f"[green]Зарплата:[/green] {v.salary}\n" if v.salary else "")
            + (f"[yellow]Локация:[/yellow]  {v.location}\n" if v.location else "")
            + (f"[cyan]Стек:[/cyan]     {v.stack}\n" if v.stack else "")
            + (f"\n[link={v.link}]{v.link}[/link]\n" if v.link else "")
            + f"\n{'─' * 60}\n\n{v.full_text}"
        )
        yield Static(text, classes="detail")
        yield Footer()


class VacancyItem(ListItem):
    def __init__(self, vacancy: Vacancy):
        super().__init__()
        self.vacancy = vacancy

    def compose(self) -> ComposeResult:
        yield Label(self._render())

    def _render(self) -> str:
        v = self.vacancy
        icon = STATUS_ICON.get(v.status, " ")
        parts = [f"{icon} [bold]{v.title}[/bold]  [dim]{v.channel} · {v.date}[/dim]"]
        row2 = "  ".join(filter(None, [
            f"[green]{v.salary}[/green]" if v.salary else None,
            f"[yellow]{v.location}[/yellow]" if v.location else None,
        ]))
        if row2:
            parts.append(row2)
        if v.stack:
            parts.append(f"[cyan]{v.stack}[/cyan]")
        if v.link:
            parts.append(f"[dim]{v.link}[/dim]")
        return "\n".join(parts)

    def refresh_label(self):
        self.query_one(Label).update(self._render())


class SearchApp(App):
    CSS = """
    VacancyItem {
        padding: 1 2;
        border-bottom: solid $panel;
    }
    VacancyItem:focus {
        background: $accent 20%;
    }
    .detail {
        padding: 1 2;
        overflow-y: auto;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Выход"),
        Binding("enter", "open_detail", "Открыть"),
        Binding("m", "mark_seen", "Прочитано"),
        Binding("f", "mark_favorite", "Избранное"),
        Binding("s", "mark_skip", "Скип"),
        Binding("u", "unmark", "Сбросить"),
    ]

    def __init__(self, vacancies: list[Vacancy], query: str, show_skipped: bool = False):
        super().__init__()
        self.all_vacancies = vacancies
        self.query_str = query
        self.show_skipped = show_skipped

    def _visible(self) -> list[Vacancy]:
        if self.show_skipped:
            return self.all_vacancies
        return [v for v in self.all_vacancies if v.status != "skipped"]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(*[VacancyItem(v) for v in self._visible()])
        yield Footer()

    def on_mount(self):
        self.title = f"Поиск: «{self.query_str}» — {len(self._visible())} результатов"

    def _current_item(self) -> Optional[VacancyItem]:
        lv = self.query_one(ListView)
        return lv.highlighted_child if lv.highlighted_child else None

    def _set_status(self, status: str):
        item = self._current_item()
        if not item:
            return
        item.vacancy.status = status
        database.set_status(item.vacancy.link, status)
        if status == "skipped" and not self.show_skipped:
            lv = self.query_one(ListView)
            lv.remove_children(f"#{item.id}")
            self.title = f"Поиск: «{self.query_str}» — {len(self._visible())} результатов"
        else:
            item.refresh_label()

    def action_open_detail(self):
        item = self._current_item()
        if item:
            if item.vacancy.status == "new":
                item.vacancy.status = "seen"
                database.set_status(item.vacancy.link, "seen")
                item.refresh_label()
            self.push_screen(DetailScreen(item.vacancy))

    def action_mark_seen(self):
        self._set_status("seen")

    def action_mark_favorite(self):
        self._set_status("favorite")

    def action_mark_skip(self):
        self._set_status("skipped")

    def action_unmark(self):
        item = self._current_item()
        if not item:
            return
        item.vacancy.status = "new"
        database.delete_status(item.vacancy.link)
        item.refresh_label()

    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        if item.vacancy.status == "new":
            item.vacancy.status = "seen"
            database.set_status(item.vacancy.link, "seen")
            item.refresh_label()
        self.push_screen(DetailScreen(item.vacancy))


def main():
    parser = argparse.ArgumentParser(description="Поиск по папке Telegram")
    parser.add_argument("query", nargs="?", help="Поисковый запрос")
    parser.add_argument("-f", "--folder", default="عمل", help="Название папки")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Макс. сообщений с канала")
    parser.add_argument("-d", "--days", type=int, help="Только за последние N дней")
    parser.add_argument("--all", dest="show_all", action="store_true", help="Показать скипнутые")
    parser.add_argument("--favorites", action="store_true", help="Показать избранное")
    args = parser.parse_args()

    if args.favorites:
        favs = database.get_favorites()
        if not favs:
            print("Избранное пусто")
            return
        for f in favs:
            print(f"{f['saved_at'][:10]}  {f['link']}")
        return

    if not args.query:
        parser.error("query обязателен (или используй --favorites)")

    vacancies = asyncio.run(fetch_results(args.query, args.folder, args.limit, args.days))

    if not args.show_all:
        vacancies = [v for v in vacancies if v.status != "skipped"]

    if not vacancies:
        print("Ничего не найдено")
        return

    app = SearchApp(vacancies, args.query, show_skipped=args.show_all)
    app.run()


if __name__ == "__main__":
    main()
