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
from operator import itemgetter
from itertools import groupby
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, deque
import yaml
try:
    from yaml import CBaseLoader as BaseLoader
except ImportError:
    from yaml import BaseLoader

import commonmark
import commonmark.node

VERSION = '5.6.0'

RE_DATE_TITLE_ARTICLE = re.compile(r"""
    ^(\d{4}-\d{2}-\d{2})    # A date in yyyy-mm-dd format at the start
    [ \t]+                  # One or more spaces or tabs
    (.*?)                   # A title. If empty, an exception will be thrown
    [ \t]*                  # Optional trailing spaces or tabs
    \n                      # A new line
    ((?:.|\n)*)             # An article
""", flags=re.VERBOSE)

RE_NAME_LABEL_DATE_TITLE_ARTICLE = re.compile(r"""
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
""", flags=re.VERBOSE)

RE_YAML_MARKDOWN = re.compile(
    r'\s*(---\n.*?\.\.\.\n)?(.*)', flags=re.DOTALL | re.MULTILINE)
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

class State(Enum):
    UNKNOWN = auto()
    DAY = auto()
    PAGE = auto()

class ParseException(Exception):
    pass

def join_year_week(year, week):
    return f'{year:04d}-{week:02d}'

def split_year_week(year_week):
    return year_week.split('-')

def split_date(date):
    return date.split('-')

def parse_date(date):
    return datetime.strptime(date, '%Y-%m-%d')

def year_week_title(fmt, year, week):
    return fmt.replace('%Y', year).replace('%V', week)

def get_year_week(date):
    year, week, _ = parse_date(date).isocalendar()
    return join_year_week(year, week)

def read_entries(filename):
    with open(filename, encoding='utf8') as f:
        entries = [item for item in
                       re.split(r'^%\n', f.read(), flags=re.MULTILINE) if item]
    if not entries:
        error('No blog entries found')
    return entries

def collect_days_and_pages(entries):

    days = []
    pages = []
    state = State.UNKNOWN

    for entry in entries:
        if (match := RE_DATE_TITLE_ARTICLE.match(entry)):
            if not match.group(2):
                error(f'A day must have a title ({match.group(1)})')
            days.append({
                'date': match.group(1),
                'title': match.group(2),
                'articles': [match.group(3)]
            })
            state = State.DAY
            continue

        if (match := RE_NAME_LABEL_DATE_TITLE_ARTICLE.match(entry)):
            if not match.group(2):
                error(f'A page must have a label (@{match.group(1)})')
            if not match.group(5):
                error(f'A page must have a title (@{match.group(1)})')
            pages.append({
                'name': match.group(1),
                'label': match.group(2),
                'date': match.group(3),
                'show-date': match.group(4) == '!',
                'title': match.group(5),
                'articles': [match.group(6)]
            })
            state = State.PAGE
            continue

        if state == State.DAY:
            days[-1]['articles'].append(entry)
            continue

        if state == State.PAGE:
            pages[-1]['articles'].append(entry)
            continue

        error('No date or page specified for first tumblelog entry')

    days.sort(key=itemgetter('date'), reverse=True)
    pages.sort(key=itemgetter('date'), reverse=True)

    return days, pages

def create_archive(days):

    seen = set()
    archive = defaultdict(deque)
    for day in days:
        year, week, _ = parse_date(day['date']).isocalendar()
        year_week = join_year_week(year, week)
        if year_week not in seen:
            archive[f'{year:04d}'].appendleft(f'{week:02d}')
            seen.add(year_week)

    return archive

def html_link_for_day(day, config):

    title = escape(day['title'])
    label = escape(parse_date(day['date']).strftime(config['date-format']))

    year, month, day_number = split_date(day['date'])
    uri = f'../../{year}/{month}/{day_number}.html'

    return f'<a href="{uri}" title="{label}">{title}</a>'

def html_for_next_prev(days, index, config):

    length = len(days)
    if length == 1:
        return ''

    html = '<nav class="tl-next-prev">\n'

    if index:
        html += ''.join([
            '  <div class="next">',
            html_link_for_day(days[index - 1], config),
            '</div>'
            '<div class="tl-right-arrow">\N{RIGHTWARDS ARROW}</div>\n'
        ])

    if index < length - 1:
        html += ''.join([
            '  <div class="tl-left-arrow">\N{LEFTWARDS ARROW}</div>'
            '<div class="prev">',
            html_link_for_day(days[index + 1], config),
            '</div>\n'
        ])

    html += '</nav>\n'

    return html

def html_for_archive(archive, current_year_week, path, label_format):
    html = '<dl>\n'
    for year in sorted(archive, reverse=True):
        html += (f'  <dt><a href="{path}/{year}/">{year}</a></dt>\n'
                 f'  <dd>\n    <ul>\n')
        for week in archive[year]:
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

def html_for_date(date, date_format, title, path):
    year, month, day = date.split('-')
    uri = f'{path}/{year}/{month}/{day}.html'

    link_text = escape(parse_date(date).strftime(date_format))
    title_text = escape(title)

    return (
        f'<time class="tl-date" datetime="{date}">'
        f'<a href="{uri}" title="{title_text}">{link_text}</a></time>\n'
    )

def rewrite_ast(ast):
    """ Rewrite an image at the start of a paragraph followed by some text
        to an image with a figcaption inside a figure element """

    for node, entering in ast.walker():
        if node.t == 'paragraph' and not entering:
            child = node.first_child
            if child and child.t == 'image' and node.last_child is not child:
                sibling = child.nxt
                if sibling.t == 'softbreak':
                    sibling.unlink()

                figcaption = commonmark.node.Node('custom_block', None)
                figcaption.on_enter = '<figcaption>'
                figcaption.on_exit = '</figcaption>'

                sibling = child.nxt
                while sibling:
                    nxt = sibling.nxt
                    figcaption.append_child(sibling) # unlinks for us
                    sibling = nxt

                figure = commonmark.node.Node('custom_block', None)
                figure.on_enter = '<figure>'
                figure.on_exit = '</figure>'
                figure.append_child(child)
                figure.append_child(figcaption)

                node.insert_before(figure)
                node.unlink()

def html_for_year_nav_bar(years, year_index, path=''):

    if year_index > 0:
        prv = years[year_index - 1]
        nav = ('    <div>\N{LEFTWARDS ARROW} '
               f'<a href="../{prv}/{path}">{prv}</a></div>\n')
    else:
        nav = '    <div></div>\n'

    nav += f'    <h2>{years[year_index]}</h2>\n'

    if year_index < len(years) - 1:
        nxt = years[year_index + 1]
        nav += (f'    <div><a href="../{nxt}/{path}">{nxt}</a> '
                '\N{RIGHTWARDS ARROW}</div>\n')
    else:
        nav += '    <div></div>\n'

    return f'  <div class="tl-year">\n{nav}  </div>\n'

def html_link_for_day_number(day):
    year, month, day_number = split_date(day['date'])
    uri = f'../{year}/{month}/{day_number}.html'
    title = escape(day['title'])
    mday = int(day_number)
    return f'<a href="{uri}" title="{title}">{mday}</a>'

def html_for_row(current_year, dt, row, week_active):

    year, week, _ = dt.isocalendar()
    if week_active:
        if year == current_year:
            week_html = f'<a href="week/{week:02d}.html">{week}</a>'
        else:
            week_html = (f'<a href="../{year:04d}/'
                         f'week/{week:02d}.html">{week}</a>')
    else:
        week_html = week

    return ''.join([
        '      <tr>\n'
        f'        <th scope="row">{week_html}</th>\n',
        *[f'        <td>{day}</td>\n' for day in row],
        '      </tr>\n'
    ])

def html_for_day_names_row():
    dt = parse_date('2019-01-07') # Monday
    names = ''
    for _ in range(7):
        day_name = dt.strftime('%a')
        names += f'        <th scope="col">{day_name}</th>\n'
        dt += timedelta(days=1)
    return f'      <tr>\n        <td></td>\n{names}      </tr>\n'

def html_for_month_nav_bar(active_months, current_month, names):
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

def html_for_day(day):
    _, _, day_number = split_date(day['date'])
    uri = f'{day_number}.html'
    title = escape(day['title'])
    return f'    <dt>{day_number}</dt><dd><a href="{uri}">{title}</a></dd>\n'

def create_page(path, title, body_html, archive_html, config,
                label, min_year, max_year):
    if min_year == max_year:
        year_range = str(min_year)
    else:
        year_range = f'{min_year}\N{EN DASH}{max_year}'

    slashes = path.count('/')
    css = ''.join(['../' * slashes, config['css']])
    uri_path = re.sub(r'\bindex\.html$', '', path)
    page_url = urllib.parse.urljoin(config['blog-url'], uri_path)

    html = config['template']
    html = RE_TITLE.sub(escape(title), html)
    html = RE_YEAR_RANGE.sub(escape(year_range), html)
    html = RE_LABEL.sub(escape(label), html)
    html = RE_CSS.sub(escape(css), html)
    html = RE_NAME.sub(escape(config['name']), html)
    html = RE_AUTHOR.sub(escape(config['author']), html)
    html = RE_DESCRIPTION.sub(escape(config['description']), html)
    html = RE_VERSION.sub(escape(VERSION), html)
    html = RE_PAGE_URL.sub(escape(page_url), html)
    html = RE_RSS_FEED_URL.sub(escape(config['rss-feed-url']), html)
    html = RE_JSON_FEED_URL.sub(escape(config['json-feed-url']), html)
    html = RE_BODY.sub(lambda _: body_html, html, count=1)
    html = RE_ARCHIVE.sub(archive_html, html)

    Path(config['output-dir']).joinpath(path).write_text(
        html, encoding='utf-8')

    if not config['quiet']:
        print(f"Created '{path}'")

def create_index(days, archive, config, min_year, max_year):
    body_html = ''

    for day in days[:config['days']]:
        body_html += html_for_date(
            day['date'], config['date-format'], day['title'], 'archive'
        ) + ''.join(article['html'] for article in day['articles'])

    archive_html = html_for_archive(
        archive, None, 'archive', config['label-format'])

    create_page(
        'index.html', 'home', body_html, archive_html, config,
        'home', min_year, max_year
    )

def create_year_pages(days, archive, config, min_year, max_year):

    start_year, *_ = split_date(days[-1]['date'])
    end_year,   *_ = split_date(days[ 0]['date'])

    start_year = int(start_year)
    end_year   = int(end_year)

    archive_html = html_for_archive(archive, None, '..', config['label-format'])

    day_names_row = html_for_day_names_row()
    dt = parse_date(f'{start_year}-01-01')
    it = reversed(days)
    day = next(it)
    date = day['date']
    for year_index, year in enumerate(range(start_year, end_year + 1)):
        body_html = ('<div class="tl-topbar"></div>\n'
            '<div class="tl-calendar">\n'
            + html_for_year_nav_bar(
                list(range(start_year, end_year + 1)), year_index))

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
                        day = next(it)
                        date = day['date']
                    except StopIteration:
                        pass
                else:
                    row[wday] = dt.day

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

            body_html += ''.join([
                '  <table class="tl-month">\n'
                f'    <caption>{caption}</caption>\n'
                '    <thead>\n',
                day_names_row,
                '    </thead>\n'
                '    <tbody>\n',
                tbody,
                '    </tbody>\n'
                '  </table>\n'
            ])

            if dt.year != year:
                break

        body_html += '</div>\n'

        Path(config['output-dir']).joinpath(f'archive/{year}').mkdir(
            parents=True, exist_ok=True)
        create_page(
            f'archive/{year}/index.html',
            str(year), body_html, archive_html, config,
            str(year), min_year, max_year
        )

def create_month_pages(days, archive, config, min_year, max_year):

    years = defaultdict(lambda: defaultdict(deque))
    for day in days:
        year, month, _ = split_date(day['date'])
        years[year][month].appendleft(day)

    month_names = get_month_names()
    archive_html = html_for_archive(
        archive, None, '../..', config['label-format'])

    for year in sorted(years):
        for month in sorted(years[year]):
            days_for_month = years[year][month]
            first_dt = parse_date(days_for_month[0]['date'])
            month_name = first_dt.strftime('%B')
            nav_bar = html_for_month_nav_bar(years[year], month, month_names)
            body_html = ''.join([
                '<div class="tl-topbar"></div>\n'
                '<div class="tl-month-overview">\n'
                f'  <h2 class="tl-month-year">{month_name} '
                f'<a href="../../{year}/">{year}</a></h2>'
                '  <dl class="tl-days">\n',
                *[html_for_day(day) for day in days_for_month],
                '  </dl>\n',
                nav_bar,
                '</div>\n'
            ])
            create_page(
                f'archive/{year}/{month}/index.html',
                f'{month_name}, {year}', body_html, archive_html, config,
                first_dt.strftime('%b, %Y'), min_year, max_year
            )

def create_week_page(year_week, body_html, archive, config, min_year, max_year):

    archive_html = html_for_archive(
        archive, year_week, '../..', config['label-format'])

    year, week = split_year_week(year_week)
    title = year_week_title(config['label-format'], year, week)

    Path(config['output-dir']).joinpath(f'archive/{year}/week').mkdir(
        parents=True, exist_ok=True)
    create_page(
        f'archive/{year}/week/{week}.html',
        title, body_html, archive_html, config,
        title, min_year, max_year
    )

def create_day_and_week_pages(days, archive, config, min_year, max_year):

    week_body_html = ''
    current_year_week = get_year_week(days[0]['date'])
    day_archive_html = html_for_archive(
        archive, None, '../..', config['label-format'])

    for day_index, day in enumerate(days):
        day_body_html = html_for_date(
            day['date'], config['date-format'], day['title'], '../..'
        ) + ''.join(article['html'] for article in day['articles'])

        label = parse_date(day['date']).strftime(config['date-format'])

        year, month, day_number = split_date(day['date'])
        next_prev_html = html_for_next_prev(days, day_index, config)

        Path(config['output-dir']).joinpath(f'archive/{year}/{month}').mkdir(
            parents=True, exist_ok=True)
        create_page(
            f'archive/{year}/{month}/{day_number}.html',
            day['title'], day_body_html + next_prev_html, day_archive_html,
            config,
            label, min_year, max_year
        )

        year_week = get_year_week(day['date'])
        if year_week == current_year_week:
            week_body_html += day_body_html
        else:
            create_week_page(
                current_year_week, week_body_html, archive, config,
                min_year, max_year
            )
            current_year_week = year_week
            week_body_html = day_body_html

    create_week_page(
        year_week, week_body_html, archive, config,
        min_year, max_year
    )

def create_pages(pages, archive, config, min_year, max_year):

    archive_html = html_for_archive(
        archive, None, 'archive', config['label-format']) if archive else ''

    for page in pages:
        date = page['date']
        link_text = escape(parse_date(date).strftime(config['date-format']))
        if page['show-date']:
            body_html = (
                f'<time class="tl-date" datetime="{date}">{link_text}</time>\n')
        else:
            body_html = '<div class="tl-topbar"></div>\n'

        body_html += ''.join(article['html'] for article in page['articles'])
        create_page(
            f"{page['name']}.html",
            page['title'], body_html, archive_html, config,
            page['label'], min_year, max_year
        )

def get_url_title_description(day, config):

    description = ''.join(article['html'] for article in day['articles'])
    year, month, day_number = split_date(day['date'])
    url = urllib.parse.urljoin(
        config['blog-url'], f'archive/{year}/{month}/{day_number}.html')

    return url, day['title'], description

def get_month_names():
    return [datetime(2019, mon, 1).strftime('%B') for mon in range(1, 13)]

def get_end_of_day(date):
    return datetime.strptime(
        f'{date} 23:59:59', '%Y-%m-%d %H:%M:%S').astimezone()

def get_cloud_size(count, min_count, max_count):
    if min_count == max_count:
        return 1

    return 1 + int(4 * log(count / min_count)
                     / log(max_count / min_count))

def create_tag_pages(days, archive, config, min_year, max_year):
    tags = defaultdict(lambda: {
        'count': 0,
        'years': defaultdict(deque),
    })
    for day in days:
        year, _, _ = split_date(day['date'])
        for article in reversed(day['articles']):
            for tag in article['tags']:
                tags[tag]['count'] += 1
                tags[tag]['years'][year].appendleft({
                    'title': article['title'],
                    'date': day['date']
                })

    archive_html = html_for_archive(
        archive, None, '../../archive', config['label-format'])

    tag_info = defaultdict(lambda: defaultdict(int))
    for tag in sorted(tags):
        years = sorted(tags[tag]['years'])
        tag_info[tag]['end_year'] = years[-1]
        tag_path = get_tag_path(tag)
        for year_index, year in enumerate(years):
            body_html = ''.join([
                '<div class="tl-topbar"></div>\n'
                '<div class="tl-tag-overview">\n',
                html_for_year_nav_bar(years, year_index, tag_path),
                f'  <h2>{tag}</h2>\n'
            ])

            for month_name, rows in groupby(
                tags[tag]['years'][year],
                key=lambda r: parse_date(r['date']).strftime('%B'),
            ):
                body_html += (
                    f'  <h3>{month_name}</h3>\n'
                    '  <dl class="tl-days">\n'
                )

                for row in rows:
                    _, _, nr = split_date(row['date'])
                    body_html += f"    <dt>{nr}</dt><dd>{row['title']}</dd>\n"
                    tag_info[tag]['count'] += 1

                body_html += '  </dl>\n'

            body_html += '</div>\n'

            Path(config['output-dir']).joinpath(f'tags/{year}/').mkdir(
                parents=True, exist_ok=True)
            create_page(
                f'tags/{year}/{tag_path}',
                tag, body_html, archive_html, config,
                tag, min_year, max_year
            )

    # Create a page with a tag cloud
    min_count = min(tag_info.values(), key=itemgetter('count'))['count']
    max_count = max(tag_info.values(), key=itemgetter('count'))['count']

    body_html = ('<div class="tl-topbar"></div>\n'
        '<div class="tl-tags-overview">\n'
        + f"  <h2>{config['tags-title']}</h2>\n"
        + '  <ul class="tl-tag-cloud">\n')

    for tag in sorted(tag_info):
        tag_path = get_tag_path(tag)
        size = get_cloud_size(tag_info[tag]['count'], min_count, max_count)
        body_html += (f'    <li class="tl-size-{size}">'
            + f'<a href="{tag_info[tag]["end_year"]}/{tag_path}">'
            + f"{tag}\N{NARROW NO-BREAK SPACE}({tag_info[tag]['count']})"
            + '</a></li>\n')

    body_html += '  </ul>\n</div>\n'

    create_page(
        'tags/index.html',
        config['tags-title'], body_html, archive_html, config,
        config['tags-label'], min_year, max_year
    )


def create_rss_feed(days, config):
    items = []
    for day in days[:config['feed-size']]:
        url, title, description = get_url_title_description(day, config)

        end_of_day = get_end_of_day(day['date'])
        # RFC #822 in USA locale
        ctime = end_of_day.ctime()
        pub_date = (f'{ctime[0:3]}, {end_of_day.day:02d} {ctime[4:7]}'
                        + end_of_day.strftime(' %Y %H:%M:%S %z'))
        items.append(
            ''.join([
                '<item>'
                '<title>', escape(title), '</title>'
                '<link>', escape(url), '</link>'
                '<guid isPermaLink="true">', escape(url), '</guid>'
                '<pubDate>', escape(pub_date), '</pubDate>'
                '<description>', escape(description), '</description>'
                '</item>'
            ])
        )

    xml = ''.join([
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">'
        '<channel>'
        '<title>', escape(config['name']), '</title>'
        '<link>', escape(config['blog-url']), '</link>'
        '<description>', escape(config['description']),'</description>'
        '<atom:link href="', escape(config['rss-feed-url']),
        '" rel="self" type="application/rss+xml" />',
        *items,
        '</channel>'
        '</rss>'
    ])
    feed_path = config['rss-path']
    p = Path(config['output-dir']).joinpath(feed_path)
    with p.open(mode='w', encoding='utf-8') as f:
        print(xml, file=f)

    if not config['quiet']:
        print(f"Created '{feed_path}'")

def create_json_feed(days, config):
    items = []
    for day in days[:config['feed-size']]:
        url, title, description = get_url_title_description(day, config)

        end_of_day = get_end_of_day(day['date'])
        date_published = str(end_of_day).replace(' ', 'T')

        items.append({
            'id':    url,
            'url':   url,
            'title': title,
            'content_html':   description,
            'date_published': date_published,
        })

    feed = {
        'version':       'https://jsonfeed.org/version/1.1',
        'title':         config['name'],
        'home_page_url': config['blog-url'],
        'feed_url':      config['json-feed-url'],
        'description':   config['description'],
        'authors': [{
            'name': config['author']
        }],
        'items': items
    }
    feed_path = config['json-path']
    p = Path(config['output-dir']).joinpath(feed_path)
    with p.open(mode='w', encoding='utf-8') as f:
        json.dump(feed, f, indent=3, ensure_ascii=False, sort_keys=True,
                  separators=(',', ': '))
        print('', file=f)

    if not config['quiet']:
        print(f"Created '{feed_path}'")


def get_tag_path(tag):
    return f"{tag.replace(' ', '-')}.html"


def extract_identifier_and_heading(ast):

    it = ast.walker()
    node, entering = it.next()
    if node.t != 'document' or not entering:
        raise ParseException(
            'Unexpected state encountered') # should never happen

    node, entering = it.next()
    if node.t != 'heading' or not entering:
        raise ParseException(
            'An article must start with a level 2 heading (none found)')

    if node.level != 2:
        raise ParseException(
            f'An article must start with a level 2 heading, not {node.level}')

    heading = commonmark.HtmlRenderer().render(node)
    heading_node = node

    text = ''
    while True:
        node, entering = it.next()
        if node.t == 'heading' and not entering:
            break
        if node.literal:
            text += node.literal

    if not text:
        raise ParseException('An article must have text after a heading')

    identifier = re.sub(r'\s+', '-', text.lower())

    heading_node.unlink() # Output the title after modification later on

    return identifier, heading


def wrap_in_permalink(string, config, date, identifier):
    year, month, day_number = split_date(date)
    safe_fragment = urllib.parse.quote(identifier, safe="/!:'?()$,+@&*%;=")
    url = urllib.parse.urljoin(
        config['blog-url'],
        f'archive/{year}/{month}/{day_number}.html#{safe_fragment}'
    )
    return f'<a href="{url}">{string}</a>'


def insert_identifier_and_add_permalink(heading, date, identifier, config):
    return ''.join([
        heading[:3],
        ' id="', escape(identifier), '">',
        wrap_in_permalink(heading[4:-6], config, date, identifier),
        heading[-6:]
    ])


def validate_identifier(identifier):
    if not isinstance(identifier, str):
        raise ParseException('identifier is not a string')
    if not identifier:
        raise ParseException('identifier can not be empty')
    if re.search(r'\s', identifier):
        raise ParseException('identifier can not contain whitespace')


def validate_tags(tags):
    if not isinstance(tags, list):
        raise ParseException('Tags must be specified as a list')

    if not tags:
        raise ParseException('At least one tag must be given')

    seen = set()
    for tag in tags:
        if not tag:
            raise ParseException('A tag must have a length')
        match = RE_TAG.match(tag)
        if not match:
            raise ParseException(f"Invalid tag '{tag}' found")
        if tag in seen:
            raise ParseException(f"Duplicate tag '{tag}' found")
        seen.add(tag)


def html_for_tag(tag, year, config):
    tag_path = get_tag_path(tag)
    url = urllib.parse.urljoin(
        config['blog-url'],
        f'tags/{year}/{tag_path}'
    )
    return f'<a href="{url}">{tag}</a>'


def html_for_tags(tags, date, config):
    year, _, _ = split_date(date)
    return ''.join([
        '<ul class="tl-tags">',
        ''.join([
            '<li>' + html_for_tag(tag, year, config) + '</li>' for tag in tags
        ]),
        '</ul>\n'
    ])


def convert_articles_with_metablock_to_html(items, config):

    ids = {}
    for item in items:
        articles = []
        for article_no, article in enumerate(item['articles'], start=1):
            try:
                if not (match := RE_YAML_MARKDOWN.match(article)).group(1):
                    raise ParseException('No mandatory YAML block found')

                # Only load the most basic YAML
                meta = yaml.load(match.group(1), Loader=yaml.BaseLoader)
                if not isinstance(meta, dict):
                    raise ParseException('YAML block must be a mapping')

                ast = commonmark.Parser().parse(match.group(2))
                identifier, heading = extract_identifier_and_heading(ast)
                custom_id = meta.get('id')
                if custom_id:
                    validate_identifier(custom_id)
                    identifier = custom_id

                # identifier must be globally unique
                if identifier in ids:
                    raise ParseException(
                        f"Duplicate id '{identifier}'"
                        f" (used later in {ids[identifier]}")
                ids[identifier] = item['date']
                if 'tags' not in meta:
                    raise ParseException('No tags are specified')
                validate_tags(meta['tags'])

                rewrite_ast(ast)
                html = ''.join([
                    '<article>\n',
                    insert_identifier_and_add_permalink(
                        heading, item['date'], identifier, config),
                    commonmark.HtmlRenderer().render(ast),
                    html_for_tags(meta['tags'], item['date'], config),
                    '</article>\n'
                ])
                articles.append({
                    'title': wrap_in_permalink(
                        heading[4:-6], config, item['date'], identifier
                    ),
                    'html': html,
                    'tags': meta['tags']
                })
            except (ParseException, yaml.parser.ParserError) as e:
                error(f"{e} in article {article_no} of {item['date']}")

        item['articles'] = articles

def convert_articles_to_html(items):
    for item in items:
        articles = []
        for article in item['articles']:
            ast = commonmark.Parser().parse(article)
            rewrite_ast(ast)
            html = ''.join([
                '<article>\n',
                commonmark.HtmlRenderer().render(ast),
                '</article>\n'
            ])
            articles.append({ 'html': html })
        item['articles'] = articles

def create_blog(config):
    days, pages = collect_days_and_pages(read_entries(config['filename']))

    if config['tags']:
        convert_articles_with_metablock_to_html(days, config)
    else:
        convert_articles_to_html(days)
    convert_articles_to_html(pages)

    max_year = datetime.now().year
    if config['min-year'] is not None:
        min_year = config['min-year']
    else:
        min_year = max_year
        if days:
            min_year = min(min_year, int((split_date(days[-1]['date']))[0]))
        if pages:
            min_year = min(min_year, int((split_date(pages[-1]['date']))[0]))

    Path(config['output-dir']).mkdir(parents=True, exist_ok=True)

    archive = create_archive(days)
    if days:
        create_index(days, archive, config, min_year, max_year)
        create_day_and_week_pages(days, archive, config, min_year, max_year)
        create_month_pages(days, archive, config, min_year, max_year)
        create_year_pages(days, archive, config, min_year, max_year)
        if config['tags']:
            create_tag_pages(days, archive, config, min_year, max_year)
        create_rss_feed(days, config)
        create_json_feed(days, config)

    create_pages(pages, archive, config, min_year, max_year)

def create_argument_parser():
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
    parser.add_argument('-t', '--template-filename', dest='template-filename',
                        help='filename of template, required',
                        metavar='TEMPLATE', required=True)
    parser.add_argument('-o', '--output-dir', dest='output-dir',
                        help='directory to store HTML files in, required',
                        metavar='HTDOCS', required=True)
    parser.add_argument('-a', '--author', dest='author',
                        help='author of the blog, required',
                        metavar='AUTHOR', required=True)
    parser.add_argument('-n', '--name', dest='name',
                        help='name of the blog, required',
                        metavar='BLOGNAME', required=True)
    parser.add_argument('--description', dest='description',
                        help='description of the blog, required',
                        metavar='DESCRIPTION', required=True)
    parser.add_argument('-b', '--blog-url', dest='blog-url',
                        help='URL of the blog, required',
                        metavar='URL', required=True)
    parser.add_argument('-d', '--days', dest='days',
                        help='number of days to show on the index;'
                        ' default: %(default)s',
                        metavar='DAYS', type=int, default=14)
    parser.add_argument('-c', '--css', dest='css',
                        help='URL of the stylesheet to use;'
                        ' default: %(default)s',
                        metavar='URL', default='styles.css')
    parser.add_argument('--date-format', dest='date-format',
                        help='how to format the date;'
                        " default: '%(default)s'",
                        metavar='FORMAT', default='%d %b %Y')
    parser.add_argument('--label-format', dest='label-format',
                        help='how to format the label;'
                        "default '%(default)s'",
                        metavar='FORMAT', default='week %V, %Y')
    parser.add_argument('--min-year', dest='min-year',
                        help='minimum year for copyright notice',
                        metavar='YEAR', type=int, default=None)
    parser.add_argument('--tags', action='store_true', dest='tags',
                        help='enable tags', default=False)
    parser.add_argument('--tags-label', dest='tags-label',
                        help='label shown on tags overview page;'
                        " default: '%(default)s'",
                        metavar='LABEL', default='tags')
    parser.add_argument('--tags-title', dest='tags-title',
                        help='title shown on tags overview page;'
                        " default: '%(default)s'",
                        metavar='TITLE', default='Tags')
    parser.add_argument('--feed-size', dest='feed-size',
                        help='number of entries in a feed',
                        metavar='SIZE', type=int, default=25)
    parser.add_argument('-q', '--quiet', action='store_true', dest='quiet',
                        help="don't show progress", default=False)
    parser.add_argument('-v', '--version', action='version', version=VERSION,
                        help='show version and exit')
    return parser

def error(message):
    print(message, file=sys.stderr)
    sys.exit(0)

def get_config():
    parser = create_argument_parser()
    arguments, args = parser.parse_known_args()
    config = vars(arguments)

    if not args:
        parser.error('Specify a filename that contains the blog entries')
    if len(args) > 1:
        print('Additional arguments have been skipped', file=sys.stderr)

    config['filename'] = args[0]
    with open(config['template-filename'], encoding='utf-8') as f:
        config['template'] = f.read()

    config['json-path'] = 'feed.json'
    config['json-feed-url'] = urllib.parse.urljoin(
        config['blog-url'], config['json-path'])
    config['rss-path'] = 'feed.rss'
    config['rss-feed-url'] = urllib.parse.urljoin(
        config['blog-url'], config['rss-path'])

    return config

locale.setlocale(locale.LC_ALL, '')
create_blog(get_config())
