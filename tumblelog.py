#!/usr/bin/env python3

import re
import sys
import json
import locale
import regex
import argparse
import urllib.parse
from math import log
from html import escape
from enum import Enum, auto
from operator import attrgetter
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, deque
from collections.abc import Sequence, Container
import yaml
try:
    from yaml import CBaseLoader as BaseLoader
except ImportError:
    from yaml import BaseLoader  # type: ignore[assignment]

import commonmark
import commonmark.node

VERSION = '6.3.0'

RE_DATE_TITLE_ARTICLE = re.compile(
    r"""
    ^(\d{4}-\d{2}-\d{2})    # A date in yyyy-mm-dd format at the start
    [ \t]+                  # One or more spaces or tabs
    (.*?)                   # A title. If empty, an exception will be thrown
    [ \t]*                  # Optional trailing spaces or tabs
    \n                      # A new line
    ((?:.|\n)*)             # An article
""",
    flags=re.VERBOSE
)

RE_NAME_LABEL_DATE_TITLE_ARTICLE = re.compile(
    r"""
    ^@([a-z0-9_-]+)         # AT sign followed by a page name at the start
    \[[ \t]*                # Start label followed by optional spaces or tabs
        (.*?)               # A label. If empty, an exception will be thrown
    [ \t]*\]                # Optional spaces or tabs followed by end label
    [ \t]+                  # One or more spaces or tabs
    (\d{4}-\d{2}-\d{2})(!?) # A date in yyyy-mm-dd format with an optional !
    [ \t]+                  # One or more spaces or tabs
    (.*?)                   # A title. If empty, an exception will be thrown
    [ \t]*                  # Optional trailing spaces or tabs
    \n                      # A new line
    ((?:.|\n)*)             # An article
""",
    flags=re.VERBOSE
)

RE_YAML_MARKDOWN = re.compile(
    r'\s*(---\n.*?\.\.\.\n)?(.*)', flags=re.DOTALL | re.MULTILINE
)
RE_TAG = regex.compile(r'^[\p{Ll}\d]+(?: [\p{Ll}\d]+)*$')

RE_TITLE           = re.compile(r'(?x) \[% \s* title         \s* %\]')
RE_YEAR_RANGE      = re.compile(r'(?x) \[% \s* year-range    \s* %\]')
RE_LABEL           = re.compile(r'(?x) \[% \s* label         \s* %\]')
RE_CSS             = re.compile(r'(?x) \[% \s* css           \s* %\]')
RE_NAME            = re.compile(r'(?x) \[% \s* name          \s* %\]')
RE_AUTHOR          = re.compile(r'(?x) \[% \s* author        \s* %\]')
RE_DESCRIPTION     = re.compile(r'(?x) \[% \s* description   \s* %\]')
RE_VERSION         = re.compile(r'(?x) \[% \s* version       \s* %\]')
RE_PAGE_URL        = re.compile(r'(?x) \[% \s* page-url      \s* %\]')
RE_RSS_FEED_URL    = re.compile(r'(?x) \[% \s* rss-feed-url  \s* %\]')
RE_JSON_FEED_URL   = re.compile(r'(?x) \[% \s* json-feed-url \s* %\]')
RE_BODY            = re.compile(r'(?x) \[% \s* body          \s* %\] \n')
RE_ARCHIVE         = re.compile(r'(?x) \[% \s* archive       \s* %\] \n')


@dataclass(frozen=True, kw_only=True)
class Config:
    template_filename: str
    output_dir: str
    author: str
    name: str
    description: str
    blog_url: str
    days: int
    css: str
    date_format: str
    label_format: str
    min_year: int
    tags: bool
    tags_label: str
    tags_title: str
    feed_size: int
    quiet: bool
    filename: str
    template: str
    json_path: str
    json_feed_url: str
    rss_path: str
    rss_feed_url: str


@dataclass(kw_only=True)
class Article:
    text: str | None
    title: str | None = None
    tags: list[str] | None = None
    html: str = ''

@dataclass(kw_only=True)
class Entry:
    date: str
    title: str
    articles: list[Article]


@dataclass(kw_only=True)
class Day(Entry):
    pass


@dataclass(kw_only=True)
class Page(Entry):
    name: str
    label: str
    show_date: bool


@dataclass(kw_only=True)
class TagEntry:
    title: str
    date: str


@dataclass
class TagInfo:
    count: int = 0
    end_year: int = 0


@dataclass(kw_only=True)
class Archive:
    years: set[str]
    years_weeks: dict[str, deque[str]]


class State(Enum):
    UNKNOWN = auto()
    DAY = auto()
    PAGE = auto()


class ParseError(Exception):
    pass


class TumblelogError(Exception):
    pass


def join_year_week(year: int, week: int) -> str:
    return f'{year:04d}-{week:02d}'


def split_year_week(year_week: str) -> tuple[str, str]:
    year, week = year_week.split('-')
    return year, week


def split_date(date: str) -> tuple[str, str, str]:
    year, month, day = date.split('-')
    return year, month, day


def parse_date(date: str) -> datetime:
    return datetime.strptime(date, '%Y-%m-%d')


def year_week_title(fmt: str, year: int | str, week: int | str) -> str:
    return fmt.replace('%Y', str(year)).replace('%V', str(week))


def get_year_week(date: str) -> str:
    year, week, _ = parse_date(date).isocalendar()
    return join_year_week(year, week)


def read_raw_entries(filename: str) -> list[str]:
    with open(filename, encoding='utf-8') as f:
        raw_entries = [
            item
            for item in re.split(r'^%\n', f.read(), flags=re.MULTILINE)
            if item
        ]
    if not raw_entries:
        raise TumblelogError('No tumblelog entries found')
    return raw_entries


def collect_days_and_pages(
        raw_entries: list[str]
) -> tuple[list[Day], list[Page]]:
    days = []
    pages = []
    dates_seen = set()
    names_seen = set()
    state = State.UNKNOWN

    for raw_entry in raw_entries:
        if match := RE_DATE_TITLE_ARTICLE.match(raw_entry):
            date, title, text = match.groups()
            if date in dates_seen:
                raise TumblelogError(f'Date must be unique: {date}')
            dates_seen.add(date)
            if not title:
                raise TumblelogError(
                    f'A day must have a title ({match.group(1)})'
                )
            days.append(
                Day(date=date, title=title, articles=[Article(text=text)])
            )
            state = State.DAY
            continue

        if match := RE_NAME_LABEL_DATE_TITLE_ARTICLE.match(raw_entry):
            name, label, date, show_date, title, text = match.groups()
            if name in names_seen:
                raise TumblelogError(f'Name must be unique: {name}')
            names_seen.add(name)
            if not label:
                raise TumblelogError(f'A page must have a label (@{name})')
            if not title:
                raise TumblelogError(f'A page must have a title (@{name})')
            pages.append(
                Page(
                    name=name,
                    label=label,
                    date=date,
                    show_date=show_date == '!',
                    title=title,
                    articles=[Article(text=text)]
                )
            )
            state = State.PAGE
            continue

        if state == State.DAY:
            days[-1].articles.append(Article(text=raw_entry))
            continue

        if state == State.PAGE:
            pages[-1].articles.append(Article(text=raw_entry))
            continue

        raise TumblelogError(
            'No date or page specified for first tumblelog entry'
        )

    if days and 'index' in names_seen:
        raise TumblelogError(
            "A page can't be named 'index' if you have a blog"
        )

    days.sort(key=attrgetter('date'), reverse=True)
    pages.sort(key=attrgetter('date'), reverse=True)

    return days, pages


def create_archive(days: list[Day]) -> Archive:
    seen: defaultdict[int, set[int]] = defaultdict(set)
    years: set[str] = set()
    years_weeks: defaultdict[str, deque[str]] = defaultdict(deque)
    for day in days:
        dt = parse_date(day.date)
        years.add(f'{dt.year:04d}')
        year, week, _ = dt.isocalendar()
        if week not in seen[year]:
            years_weeks[f'{year:04d}'].appendleft(f'{week:02d}')
            seen[year].add(week)

    return Archive(years=years, years_weeks=years_weeks)


def html_link_for_day(day: Day, config: Config) -> str:
    title = escape(day.title)
    label = escape(parse_date(day.date).strftime(config.date_format))

    year, month, day_number = split_date(day.date)
    uri = f'../../{year}/{month}/{day_number}.html'

    return f'<a href="{uri}" title="{label}">{title}</a>'


def html_for_next_prev(
    days: list[Day], index: int, config: Config
) -> str:
    length = len(days)
    if length == 1:
        return ''

    html = '<nav class="tl-next-prev">\n'

    if index:
        html += (
            '  <div class="next">'
            f'{html_link_for_day(days[index - 1], config)}'
            '</div>'
            '<div class="tl-right-arrow">\N{RIGHTWARDS ARROW}</div>\n'
        )

    if index < length - 1:
        html += (
            '  <div class="tl-left-arrow">\N{LEFTWARDS ARROW}</div>'
            '<div class="prev">'
            f'{html_link_for_day(days[index + 1], config)}'
            '</div>\n'
        )

    html += '</nav>\n'

    return html


def html_for_archive(
    archive: Archive,
    current_year_week: str | None,
    path: str,
    label_format: str
) -> str:
    html = '<dl>\n'
    for year in sorted(archive.years_weeks, reverse=True):
        if year in archive.years:
            html += f'  <dt><a href="{path}/{year}/">{year}</a></dt>\n'
        else:
            html += f'  <dt class="tl-self">{year}</dt>\n'
        html += '  <dd>\n    <ul>\n'
        for week in archive.years_weeks[year]:
            year_week = join_year_week(int(year), int(week))
            if year_week == current_year_week:
                html += f'      <li class="tl-self">{week}</li>\n'
            else:
                title = escape(year_week_title(label_format, year, week))
                uri = f'{path}/{year}/week/{week}.html'
                html += (
                    '      <li>'
                    f'<a href="{uri}" title="{title}">{week}</a></li>\n'
                )
        html += '    </ul>\n  </dd>\n'
    html += '</dl>\n'

    return html


def html_for_date(date: str, date_format: str, title: str, path: str) -> str:
    year, month, day = date.split('-')
    uri = f'{path}/{year}/{month}/{day}.html'

    link_text = escape(parse_date(date).strftime(date_format))
    title_text = escape(title)

    return (
        f'<time class="tl-date" datetime="{date}">'
        f'<a href="{uri}" title="{title_text}">{link_text}</a></time>\n'
    )


def rewrite_ast(ast: commonmark.node.Node) -> None:
    """Rewrite an image at the start of a paragraph followed by some text
    to an image with a figcaption inside a figure element."""

    for node, entering in ast.walker():
        if node.t == 'paragraph' and not entering:
            child = node.first_child
            if child and child.t == 'image' and node.last_child is not child:
                sibling = child.nxt
                if sibling is not None and sibling.t == 'softbreak':
                    sibling.unlink()

                figcaption = commonmark.node.Node('custom_block', None)
                figcaption.on_enter = '<figcaption>'
                figcaption.on_exit = '</figcaption>'

                sibling = child.nxt
                while sibling:
                    nxt = sibling.nxt
                    figcaption.append_child(sibling)  # unlinks for us
                    sibling = nxt

                figure = commonmark.node.Node('custom_block', None)
                figure.on_enter = '<figure>'
                figure.on_exit = '</figure>'
                figure.append_child(child)
                figure.append_child(figcaption)

                node.insert_before(figure)
                node.unlink()


def html_for_year_nav_bar(
    years: list[int], year_index: int, path: str = ''
) -> str:
    if year_index > 0:
        prev_year = years[year_index - 1]
        nav = (
            '    <div>\N{LEFTWARDS ARROW} '
            f'<a href="../{prev_year:04d}/{path}">{prev_year}</a></div>\n'
        )
    else:
        nav = '    <div></div>\n'

    nav += f'    <h2>{years[year_index]}</h2>\n'

    if year_index < len(years) - 1:
        next_year = years[year_index + 1]
        nav += (
            f'    <div><a href="../{next_year:04d}/{path}">{next_year}</a> '
            '\N{RIGHTWARDS ARROW}</div>\n'
        )
    else:
        nav += '    <div></div>\n'

    return f'  <div class="tl-year">\n{nav}  </div>\n'


def html_link_for_day_number(day: Day) -> str:
    year, month, day_number = split_date(day.date)
    uri = f'../{year}/{month}/{day_number}.html'
    title = escape(day.title)
    mday = int(day_number)
    return f'<a href="{uri}" title="{title}">{mday}</a>'


def html_for_row(
    current_year: int, dt: datetime, row: list[str], week_active: bool
) -> str:
    year, week, _ = dt.isocalendar()
    if week_active:
        if year == current_year:
            week_html = f'<a href="week/{week:02d}.html">{week}</a>'
        else:
            week_html = (
                f'<a href="../{year:04d}/week/{week:02d}.html">{week}</a>'
            )
    else:
        week_html = str(week)

    return ''.join(
        [
            '      <tr>\n'
            f'        <th scope="row">{week_html}</th>\n',
            *(f'        <td>{day}</td>\n' for day in row),
            '      </tr>\n'
        ]
    )


def html_for_day_names_row() -> str:
    dt = parse_date('2019-01-07')  # Monday
    names = ''
    for _ in range(7):
        day_name = dt.strftime('%a')
        names += f'        <th scope="col">{day_name}</th>\n'
        dt += timedelta(days=1)
    return f'      <tr>\n        <td></td>\n{names}      </tr>\n'


def html_for_month_nav_bar(
    active_months: Container[str], current_month: str, names: list[str]
) -> str:
    html = '  <nav>\n    <ul class="tl-month-navigation">\n'
    for mon in range(1, 13):
        month = f'{mon:02d}'
        name = names[mon - 1]
        if month in active_months:
            if month == current_month:
                html += f'      <li class="tl-self">{name}</li>\n'
            else:
                html += f'      <li><a href="../{month}/">{name}</a></li>\n'
        else:
            html += f'      <li>{name}</li>\n'

    html += '    </ul>\n  </nav>\n'
    return html


def html_for_day(day: Day) -> str:
    _, _, day_number = split_date(day.date)
    uri = f'{day_number}.html'
    title = escape(day.title)
    return f'    <dt>{day_number}</dt><dd><a href="{uri}">{title}</a></dd>\n'


def create_page(
    path: str,
    title: str,
    body_html: str,
    archive_html: str,
    config: Config,
    label: str,
    min_year: int,
    max_year: int
) -> None:
    if min_year == max_year:
        year_range = str(min_year)
    else:
        year_range = f'{min_year}\N{EN DASH}{max_year}'

    slashes = path.count('/')
    css = ''.join(['../' * slashes, config.css])
    uri_path = re.sub(r'\bindex\.html$', '', path)
    page_url = urllib.parse.urljoin(config.blog_url, uri_path)

    html = config.template

    replacements = {
        RE_TITLE: escape(title),
        RE_YEAR_RANGE: escape(year_range),
        RE_LABEL: escape(label),
        RE_CSS: escape(css),
        RE_NAME: escape(config.name),
        RE_AUTHOR: escape(config.author),
        RE_DESCRIPTION: escape(config.description),
        RE_VERSION: escape(VERSION),
        RE_PAGE_URL: escape(page_url),
        RE_RSS_FEED_URL: escape(config.rss_feed_url),
        RE_JSON_FEED_URL: escape(config.json_feed_url),
    }

    for regexpr, replacement in replacements.items():
        html = regexpr.sub(replacement, html)

    html = RE_BODY.sub(lambda _: body_html, html, count=1)
    html = RE_ARCHIVE.sub(archive_html, html)

    (Path(config.output_dir) / path).write_text(html, encoding='utf-8')

    if not config.quiet:
        print(f"Created '{path}'")


def create_index(
    days: list[Day],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    body_html = ''

    for day in days[: config.days]:
        body_html += html_for_date(
            day.date, config.date_format, day.title, 'archive'
        ) + ''.join(article.html for article in day.articles)

    archive_html = html_for_archive(
        archive, None, 'archive', config.label_format
    )

    create_page(
        'index.html',
        'home',
        body_html,
        archive_html,
        config,
        'home',
        min_year,
        max_year
    )


def create_year_pages(
    days: list[Day],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    start_year, *_ = split_date(days[-1].date)
    end_year,   *_ = split_date(days[ 0].date)

    years = list(range(int(start_year), int(end_year) + 1))

    archive_html = html_for_archive(
        archive, None, '..', config.label_format
    )

    day_names_row = html_for_day_names_row()
    dt = parse_date(f'{start_year}-01-01')
    iterator = reversed(days)
    day = next(iterator)
    date = day.date
    for year_index, year in enumerate(years):
        body_html = (
            '<div class="tl-topbar"></div>\n'
            '<div class="tl-calendar">\n'
            + html_for_year_nav_bar(years, year_index)
        )

        while True:
            tbody = ''
            week_active = False
            month_active = False
            current_mon = dt.month
            month_name = dt.strftime('%B')
            row = [''] * 7
            while True:
                wday = dt.weekday()
                if date == dt.strftime('%Y-%m-%d'):
                    month_active = True
                    week_active = True
                    row[wday] = html_link_for_day_number(day)
                    try:
                        day = next(iterator)
                        date = day.date
                    except StopIteration:
                        pass
                else:
                    row[wday] = str(dt.day)

                if wday == 6:
                    tbody += html_for_row(year, dt, row, week_active)
                    week_active = False
                    row = [''] * 7

                dt += timedelta(days=1)
                if dt.month != current_mon:
                    break

            if wday < 6:
                tbody += html_for_row(year, dt, row, week_active)

            if month_active:
                caption = f'<a href="{current_mon:02d}/">{month_name}</a>'
            else:
                caption = month_name

            body_html += (
                '  <table class="tl-month">\n'
                f'    <caption>{caption}</caption>\n'
                '    <thead>\n'
                f'{day_names_row}'
                '    </thead>\n'
                '    <tbody>\n'
                f'{tbody}'
                '    </tbody>\n'
                '  </table>\n'
            )

            if dt.year != year:
                break

        body_html += '</div>\n'

        (Path(config.output_dir) / 'archive' / f'{year:04d}').mkdir(
            parents=True, exist_ok=True
        )
        create_page(
            f'archive/{year}/index.html',
            str(year),
            body_html,
            archive_html,
            config,
            str(year),
            min_year,
            max_year
        )


def create_month_pages(
    days: list[Day],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    years: defaultdict[str, defaultdict[str, deque[Day]]] = defaultdict(
        lambda: defaultdict(deque)
    )
    for day in days:
        year, month, _ = split_date(day.date)
        years[year][month].appendleft(day)

    month_names = get_month_names()
    archive_html = html_for_archive(
        archive, None, '../..', config.label_format
    )

    for year in sorted(years):
        for month in sorted(years[year]):
            days_for_month = years[year][month]
            first_dt = parse_date(days_for_month[0].date)
            month_name = first_dt.strftime('%B')
            nav_bar = html_for_month_nav_bar(years[year], month, month_names)
            body_html = ''.join(
                [
                    '<div class="tl-topbar"></div>\n'
                    '<div class="tl-month-overview">\n'
                    f'  <h2 class="tl-month-year">{month_name} '
                    f'<a href="../../{year}/">{year}</a></h2>'
                    '  <dl class="tl-days">\n',
                    *(html_for_day(day) for day in days_for_month),
                    '  </dl>\n'
                    f'{nav_bar}'
                    '</div>\n'
                ]
            )
            create_page(
                f'archive/{year}/{month}/index.html',
                f'{month_name}, {year}',
                body_html,
                archive_html,
                config,
                first_dt.strftime('%b, %Y'),
                min_year,
                max_year
            )


def create_week_page(
    year_week: str,
    body_html: str,
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    archive_html = html_for_archive(
        archive, year_week, '../..', config.label_format
    )

    year, week = split_year_week(year_week)
    title = year_week_title(config.label_format, year, week)

    (Path(config.output_dir) / 'archive' / year / 'week').mkdir(
        parents=True, exist_ok=True
    )
    create_page(
        f'archive/{year}/week/{week}.html',
        title,
        body_html,
        archive_html,
        config,
        title,
        min_year,
        max_year
    )


def create_day_and_week_pages(
    days: list[Day],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    week_body_html = ''
    current_year_week = get_year_week(days[0].date)
    day_archive_html = html_for_archive(
        archive, None, '../..', config.label_format
    )

    for day_index, day in enumerate(days):
        day_body_html = html_for_date(
            day.date, config.date_format, day.title, '../..'
        ) + ''.join(article.html for article in day.articles)

        label = parse_date(day.date).strftime(config.date_format)

        year, month, day_number = split_date(day.date)
        next_prev_html = html_for_next_prev(days, day_index, config)

        (Path(config.output_dir) / 'archive' / year / month).mkdir(
            parents=True, exist_ok=True
        )
        create_page(
            f'archive/{year}/{month}/{day_number}.html',
            day.title,
            day_body_html + next_prev_html,
            day_archive_html,
            config,
            label,
            min_year,
            max_year
        )

        year_week = get_year_week(day.date)
        if year_week == current_year_week:
            week_body_html += day_body_html
        else:
            create_week_page(
                current_year_week,
                week_body_html,
                archive,
                config,
                min_year,
                max_year
            )
            current_year_week = year_week
            week_body_html = day_body_html

    create_week_page(
        year_week,
        week_body_html,
        archive,
        config,
        min_year,
        max_year
    )


def create_pages(
    pages: list[Page],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    archive_html = (
        html_for_archive(archive, None, 'archive', config.label_format)
        if archive
        else ''
    )
    for page in pages:
        date = page.date
        link_text = escape(parse_date(date).strftime(config.date_format))
        if page.show_date:
            body_html = (
                f'<time class="tl-date" datetime="{date}">{link_text}</time>\n'
            )
        else:
            body_html = '<div class="tl-topbar"></div>\n'

        body_html += ''.join(article.html for article in page.articles)

        create_page(
            f"{page.name}.html",
            page.title,
            body_html,
            archive_html,
            config,
            page.label,
            min_year,
            max_year
        )


def get_url_title_description(
    day: Day,
    config: Config
) -> tuple[str, str, str]:
    description = ''.join(article.html for article in day.articles)
    year, month, day_number = split_date(day.date)
    url = urllib.parse.urljoin(
        config.blog_url, f'archive/{year}/{month}/{day_number}.html'
    )
    return url, day.title, description


def get_month_names() -> list[str]:
    return [datetime(2019, month, 1).strftime('%B') for month in range(1, 13)]


def get_end_of_day(date: str) -> datetime:
    return datetime.strptime(
        f'{date} 23:59:59', '%Y-%m-%d %H:%M:%S'
    ).astimezone()


def get_cloud_size(count: int, min_count: int, max_count: int) -> int:
    if min_count == max_count:
        return 1
    return 1 + int(4 * log(count / min_count) / log(max_count / min_count))


def create_tag_pages(
    days: list[Day],
    archive: Archive,
    config: Config,
    min_year: int,
    max_year: int
) -> None:
    tag_years: defaultdict[
        str, defaultdict[int, deque[TagEntry]]
    ] = defaultdict(lambda: defaultdict(deque))

    for day in days:
        year_str, _, _ = split_date(day.date)
        for article in reversed(day.articles):
            if article.tags is None:
                raise RuntimeError('Unexpected: article.tags is None')
            for tag in article.tags:
                if article.title is None:
                    raise RuntimeError('Unexpected: article.title is None')
                tag_years[tag][int(year_str)].appendleft(
                    TagEntry(title=article.title, date=day.date)
                )

    archive_html = html_for_archive(
        archive, None, '../../archive', config.label_format
    )

    tag_info: defaultdict[str, TagInfo] = defaultdict(TagInfo)
    for tag in sorted(tag_years):
        years = sorted(tag_years[tag])
        tag_info[tag].end_year = years[-1]
        tag_path = get_tag_path(tag)
        for year_index, year in enumerate(years):
            body_html = (
                '<div class="tl-topbar"></div>\n'
                '<div class="tl-tag-overview">\n'
                f'{html_for_year_nav_bar(years, year_index, tag_path)}'
                f'  <h2>{tag}</h2>\n'
            )

            for month_name, rows in groupby(
                tag_years[tag][year],
                key=lambda r: parse_date(r.date).strftime('%B'),
            ):
                body_html += (
                    f'  <h3>{month_name}</h3>\n'
                    '  <dl class="tl-days">\n'
                )

                for row in rows:
                    _, _, day_number = split_date(row.date)
                    body_html += (
                        f"    <dt>{day_number}</dt><dd>{row.title}</dd>\n"
                    )
                    tag_info[tag].count += 1

                body_html += '  </dl>\n'

            body_html += '</div>\n'

            (Path(config.output_dir) / 'tags' / f'{year:04d}').mkdir(
                parents=True, exist_ok=True
            )
            create_page(
                f'tags/{year:04d}/{tag_path}',
                tag,
                body_html,
                archive_html,
                config,
                tag,
                min_year,
                max_year
            )

    # Create a page with a tag cloud
    min_count = min(tag_info.values(), key=attrgetter('count')).count
    max_count = max(tag_info.values(), key=attrgetter('count')).count

    body_html = (
        '<div class="tl-topbar"></div>\n'
        '<div class="tl-tags-overview">\n'
        f"  <h2>{config.tags_title}</h2>\n"
        '  <ul class="tl-tag-cloud">\n'
    )

    for tag in sorted(tag_info):
        tag_info_entry = tag_info[tag]
        tag_path = get_tag_path(tag)
        size = get_cloud_size(tag_info_entry.count, min_count, max_count)
        body_html += (
            f'    <li class="tl-size-{size}">'
            f'<a href="{tag_info_entry.end_year:04d}/{tag_path}">'
            f"{tag}\N{NARROW NO-BREAK SPACE}({tag_info_entry.count})"
            '</a></li>\n'
        )

    body_html += '  </ul>\n</div>\n'

    create_page(
        'tags/index.html',
        config.tags_title,
        body_html,
        archive_html,
        config,
        config.tags_label,
        min_year,
        max_year
    )


def create_rss_feed(days: list[Day], config: Config) -> None:
    items = []
    for day in days[: config.feed_size]:
        url, title, description = get_url_title_description(day, config)

        end_of_day = get_end_of_day(day.date)
        # RFC #822 in USA locale
        ctime = end_of_day.ctime()
        pub_date = (
            f'{ctime[0:3]}, {end_of_day.day:02d} {ctime[4:7]}'
            + end_of_day.strftime(' %Y %H:%M:%S %z')
        )
        items.append(
            (
                '<item>'
                f'<title>{escape(title)}</title>'
                f'<link>{escape(url)}</link>'
                f'<guid isPermaLink="true">{escape(url)}</guid>'
                f'<pubDate>{escape(pub_date)}</pubDate>'
                f'<description>{escape(description)}</description>'
                '</item>'
            )
        )

    xml = ''.join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
            '<channel>'
            f'<title>{escape(config.name)}</title>'
            f'<link>{escape(config.blog_url)}</link>'
            f'<description>{escape(config.description)}</description>'
            f'<atom:link href="{escape(config.rss_feed_url)}"'
            ' rel="self" type="application/rss+xml" />',
            *items,
            '</channel>'
            '</rss>\n'
        ]
    )
    feed_path = Path(config.output_dir) / config.rss_path
    feed_path.write_text(xml, encoding='utf-8')

    if not config.quiet:
        print(f"Created '{feed_path}'")


def create_json_feed(days: list[Day], config: Config) -> None:
    items = []
    for day in days[: config.feed_size]:
        url, title, description = get_url_title_description(day, config)

        end_of_day = get_end_of_day(day.date)
        date_published = str(end_of_day).replace(' ', 'T')

        items.append(
            {
                'id': url,
                'url': url,
                'title': title,
                'content_html': description,
                'date_published': date_published,
            }
        )

    feed = {
        'version': 'https://jsonfeed.org/version/1.1',
        'title': config.name,
        'home_page_url': config.blog_url,
        'feed_url': config.json_feed_url,
        'description': config.description,
        'authors': [{'name': config.author}],
        'items': items
    }
    feed_path = Path(config.output_dir) / config.json_path
    feed_path.write_text(
        json.dumps(
            feed,
            indent=3,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ': ')
        ) + '\n',
        encoding='utf-8'
    )

    if not config.quiet:
        print(f"Created '{feed_path}'")


def get_tag_path(tag: str) -> str:
    return f"{tag.replace(' ', '-')}.html"


def extract_identifier_and_heading(
    ast: commonmark.node.Node
) -> tuple[str, str]:
    iterator = ast.walker()
    node, entering = iterator.next()
    if node.t != 'document' or not entering:
        raise ParseError('Unexpected state encountered')  # should never happen

    node, entering = iterator.next()
    if node.t != 'heading' or not entering:
        raise ParseError(
            'An article must start with a level 2 heading (none found)'
        )

    if node.level != 2:
        raise ParseError(
            f'An article must start with a level 2 heading, not {node.level}'
        )

    heading = commonmark.HtmlRenderer().render(node)
    heading_node = node

    text = ''
    while True:
        node, entering = iterator.next()
        if node.t == 'heading' and not entering:
            break
        if node.literal:
            text += node.literal

    if not text:
        raise ParseError('An article must have text after a heading')

    identifier = re.sub(r'\s+', '-', text.lower())

    heading_node.unlink()  # Output the title after modification later on

    return identifier, heading


def wrap_in_permalink(
    string: str,
    config: Config,
    date: str,
    identifier: str
) -> str:
    year, month, day_number = split_date(date)
    safe_fragment = urllib.parse.quote(identifier, safe="/!:'?()$,+@&*%;=")
    url = urllib.parse.urljoin(
        config.blog_url,
        f'archive/{year}/{month}/{day_number}.html#{safe_fragment}'
    )
    return f'<a href="{url}">{string}</a>'


def insert_identifier_and_add_permalink(
    heading: str,
    date: str,
    identifier: str,
    config: Config
) -> str:
    return (
        f'{heading[:3]} id="{escape(identifier)}">'
        f'{wrap_in_permalink(heading[4:-6], config, date, identifier)}'
        f'{heading[-6:]}'
    )


def validate_identifier(identifier: str) -> None:
    if not isinstance(identifier, str):
        raise ParseError('identifier is not a string')
    if not identifier:
        raise ParseError('identifier must not be empty')
    if re.search(r'\s', identifier):
        raise ParseError('identifier must not contain whitespace')


def validate_tags(tags: object) -> None:
    if not isinstance(tags, list):
        raise ParseError('Tags must be specified as a list')

    if not tags:
        raise ParseError('At least one tag must be given')

    seen = set()
    for tag in tags:
        if not tag:
            raise ParseError('A tag must have a length')
        match = RE_TAG.match(tag)
        if not match:
            raise ParseError(f"Invalid tag: '{tag}'")
        if tag in seen:
            raise ParseError(f"Duplicate tag: '{tag}'")
        seen.add(tag)


def html_for_tag(tag: str, year: str, config: Config) -> str:
    tag_path = get_tag_path(tag)
    url = urllib.parse.urljoin(config.blog_url, f'tags/{year}/{tag_path}')
    return f'<a href="{url}">{tag}</a>'


def html_for_tags(tags: list[str], date: str, config: Config) -> str:
    year, _, _ = split_date(date)
    tag_items = ''.join(
        f'<li>{html_for_tag(tag, year, config)}</li>' for tag in tags
    )
    return f'<ul class="tl-tags">{tag_items}</ul>\n'


def convert_day_articles_with_metablock_to_html(
    days: list[Day],
    config: Config
) -> None:
    ids: dict[str, str] = {}
    parser = commonmark.Parser()
    renderer = commonmark.HtmlRenderer()
    for day in days:
        for article_no, article in enumerate(day.articles, start=1):
            try:
                if article.text is None:
                    raise RuntimeError('Unexpected: article.text is None')
                match = RE_YAML_MARKDOWN.match(article.text)
                if match is None:
                    raise RuntimeError('Unexpected: no match occurred')
                yaml_block, markdown = match.groups()
                if not yaml_block:
                    raise ParseError('No mandatory YAML block found')

                # Only load the most basic YAML
                meta = yaml.load(yaml_block, Loader=BaseLoader)
                if not isinstance(meta, dict):
                    raise ParseError('YAML block must be a mapping')

                ast = parser.parse(markdown)
                identifier, heading = extract_identifier_and_heading(ast)
                if custom_id := meta.get('id'):
                    validate_identifier(custom_id)
                    identifier = custom_id

                # identifier must be globally unique
                if identifier in ids:
                    raise ParseError(
                        f"Duplicate id '{identifier}'"
                        f' (used later in {ids[identifier]})'
                    )
                ids[identifier] = day.date
                if 'tags' not in meta:
                    raise ParseError('No tags are specified')
                validate_tags(meta['tags'])

                rewrite_ast(ast)
                permalink_heading = insert_identifier_and_add_permalink(
                    heading, day.date, identifier, config
                )

                article.title = wrap_in_permalink(
                    heading[4:-6], config, day.date, identifier
                )
                article.html = (
                    '<article>\n'
                    f'{permalink_heading}'
                    f'{renderer.render(ast)}'
                    f"{html_for_tags(meta['tags'], day.date, config)}"
                    '</article>\n'
                )
                article.tags = meta['tags']
                article.text = None
            except (ParseError, yaml.parser.ParserError) as e:
                raise TumblelogError(
                    f"{e} in article {article_no} of {day.date}"
                )


def convert_entry_articles_to_html(entries: Sequence[Entry]) -> None:
    parser = commonmark.Parser()
    renderer = commonmark.HtmlRenderer()
    for entry in entries:
        for article in entry.articles:
            if article.text is None:
                raise RuntimeError('Unexpected: article.text is None')
            ast = parser.parse(article.text)
            rewrite_ast(ast)
            article.html = f'<article>\n{renderer.render(ast)}</article>\n'
            article.text = None


def create_blog(config: Config) -> None:
    days, pages = collect_days_and_pages(read_raw_entries(config.filename))

    if config.tags:
        convert_day_articles_with_metablock_to_html(days, config)
    else:
        convert_entry_articles_to_html(days)
    convert_entry_articles_to_html(pages)

    max_year = datetime.now().year
    if config.min_year is not None:
        min_year = config.min_year
    else:
        min_year = max_year
        if days:
            min_year = min(min_year, int((split_date(days[-1].date))[0]))
        if pages:
            min_year = min(min_year, int((split_date(pages[-1].date))[0]))

    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    archive = create_archive(days)
    create_pages(pages, archive, config, min_year, max_year)

    if not days:
        return

    create_index(days, archive, config, min_year, max_year)
    create_day_and_week_pages(days, archive, config, min_year, max_year)
    create_month_pages(days, archive, config, min_year, max_year)
    create_year_pages(days, archive, config, min_year, max_year)
    if config.tags:
        create_tag_pages(days, archive, config, min_year, max_year)
    create_rss_feed(days, config)
    create_json_feed(days, config)


def create_argument_parser() -> argparse.ArgumentParser:
    usage = """
  %(prog)s --template-filename TEMPLATE --output-dir HTDOCS
      --author AUTHOR --name BLOGNAME --description DESCRIPTION
      --blog-url URL
      [--days DAYS ] [--css URL] [--date-format DATE] [--min-year YEAR]
      [--tags [--tags-label LABEL] [--tags-title TITLE]]
      [--quiet] FILE
  %(prog)s --version
  %(prog)s --help"""

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument(
        '-t',
        '--template-filename',
        dest='template_filename',
        help='filename of template, required',
        metavar='TEMPLATE',
        required=True
    )
    parser.add_argument(
        '-o',
        '--output-dir',
        dest='output_dir',
        help='directory to store HTML files in, required',
        metavar='HTDOCS',
        required=True
    )
    parser.add_argument(
        '-a',
        '--author',
        dest='author',
        help='author of the blog, required',
        metavar='AUTHOR',
        required=True
    )
    parser.add_argument(
        '-n',
        '--name',
        dest='name',
        help='name of the blog, required',
        metavar='BLOGNAME',
        required=True
    )
    parser.add_argument(
        '--description',
        dest='description',
        help='description of the blog, required',
        metavar='DESCRIPTION',
        required=True
    )
    parser.add_argument(
        '-b',
        '--blog-url',
        dest='blog_url',
        help='URL of the blog, required',
        metavar='URL',
        required=True
    )
    parser.add_argument(
        '-d',
        '--days',
        dest='days',
        help='number of days to show on the index; default: %(default)s',
        metavar='DAYS',
        type=int,
        default=14
    )
    parser.add_argument(
        '-c',
        '--css',
        dest='css',
        help='URL of the stylesheet to use; default: %(default)s',
        metavar='URL',
        default='styles.css'
    )
    parser.add_argument(
        '--date-format',
        dest='date_format',
        help="how to format the date; default: '%(default)s'",
        metavar='FORMAT',
        default='%d %b %Y'
    )
    parser.add_argument(
        '--label-format',
        dest='label_format',
        help="how to format the label; default '%(default)s'",
        metavar='FORMAT',
        default='week %V, %Y'
    )
    parser.add_argument(
        '--min-year',
        dest='min_year',
        help='minimum year for copyright notice',
        metavar='YEAR',
        type=int,
        default=None
    )
    parser.add_argument(
        '--tags',
        action='store_true',
        dest='tags',
        help='enable tags',
        default=False
    )
    parser.add_argument(
        '--tags-label',
        dest='tags_label',
        help="label shown on tags overview page; default: '%(default)s'",
        metavar='LABEL',
        default='tags'
    )
    parser.add_argument(
        '--tags-title',
        dest='tags_title',
        help="title shown on tags overview page; default: '%(default)s'",
        metavar='TITLE',
        default='Tags'
    )
    parser.add_argument(
        '--feed-size',
        dest='feed_size',
        help='number of entries in a feed',
        metavar='SIZE',
        type=int,
        default=25
    )
    parser.add_argument(
        '-q',
        '--quiet',
        action='store_true',
        dest='quiet',
        help="don't show progress",
        default=False
    )
    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=VERSION,
        help='show version and exit'
    )
    return parser


def get_config() -> Config:
    parser = create_argument_parser()
    arguments, args = parser.parse_known_args()
    config = vars(arguments)

    if not args:
        parser.error('Specify a filename that contains the blog entries')
    if len(args) > 1:
        print('Additional arguments have been skipped', file=sys.stderr)

    with open(config['template_filename'], encoding='utf-8') as f:
        template = f.read()

    json_path = 'feed.json'
    rss_path = 'feed.rss'

    return Config(
        **config,
        filename=args[0],
        template=template,
        json_path=json_path,
        json_feed_url=urllib.parse.urljoin(
            config['blog_url'], json_path
        ),
        rss_path=rss_path,
        rss_feed_url=urllib.parse.urljoin(
            config['blog_url'], rss_path
        )
    )


if __name__ == '__main__':
    locale.setlocale(locale.LC_ALL, '')  # use locale from OS/environment
    try:
        create_blog(get_config())
    except TumblelogError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
