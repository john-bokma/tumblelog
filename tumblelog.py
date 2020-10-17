#!/usr/bin/env python3

import re
import sys
import json
import locale
import argparse
import urllib.parse
from html import escape
from operator import itemgetter
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, deque

import commonmark
import commonmark.node

VERSION = '4.1.0'

RE_DATE_TITLE = re.compile(r'(\d{4}-\d{2}-\d{2})(.*?)\n(.*)', flags=re.DOTALL)
RE_AT_PAGE_TITLE = re.compile(
    r'@([a-z0-9_-]+)\[(.+)\]\s+(\d{4}-\d{2}-\d{2})(!?)(.*?)\n(.*)',
    flags=re.DOTALL)

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


class NoEntriesError(Exception):
    """Thrown in case there are no blog entries; the file is empty"""

class BadEntry(Exception):
    """Thrown in case the blog entry can not be handled"""

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
    return join_year_week(*parse_date(date).isocalendar()[0:2])

def read_tumblelog_entries(filename):
    with open(filename, encoding='utf8') as f:
        entries = [item for item in
                       re.split(r'^%\n', f.read(), flags=re.MULTILINE) if item]
    if not entries:
        raise NoEntriesError('No blog entries found')

    return entries

def collect_days_and_pages(entries):

    days = deque()
    pages = deque()
    state = 'unknown'

    for entry in entries:
        match = RE_DATE_TITLE.match(entry)
        if match:
            title = match.group(2).strip()
            if not title:
                raise BadEntry(f'A day must have a title ({match.group(1)})')
            days.append({
                'date': match.group(1),
                'title': title,
                'entries': [match.group(3)]
            })
            state = 'date-title'
            continue

        match = RE_AT_PAGE_TITLE.match(entry)
        if match:
            title = match.group(5).strip()
            if not title:
                raise BadEntry(f'A page must have a title (@{match.group(1)})')
            pages.append({
                'name': match.group(1),
                'label': match.group(2).strip(),
                'date': match.group(3),
                'show-date': match.group(4) == '!',
                'title': title,
                'entries': [match.group(6)]
            })
            state = 'at-page-title'
            continue

        if state == 'date-title':
            days[-1]['entries'].append(entry)
            continue

        if state == 'at-page-title':
            pages[-1]['entries'].append(entry)
            continue

        raise BadEntry('No date or page specified for first tumblelog entry')

    days  = sorted(days,  key=itemgetter('date'), reverse=True)
    pages = sorted(pages, key=itemgetter('date'), reverse=True)

    return days, pages

def create_archive(days):

    seen = {}
    archive = defaultdict(deque)
    for day in days:
        year, week = parse_date(day['date']).isocalendar()[0:2]
        year_week = join_year_week(year, week)
        if year_week not in seen:
            archive[f'{year:04d}'].appendleft(f'{week:02d}')
            seen[year_week] = 1

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
            '<div class="tl-right-arrow">\u2192</div>\n'
        ])

    if index < length - 1:
        html += ''.join([
            '  <div class="tl-left-arrow">\u2190</div>'
            '<div class="prev">',
            html_link_for_day(days[index + 1], config),
            '</div>\n'
        ])

    html += '</nav>\n'

    return html

def html_for_archive(archive, current_year_week, path, label_format):
    html = '<dl>\n'
    for year in sorted(archive.keys(), reverse=True):
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

def html_for_entry(entry):
    ast = commonmark.Parser().parse(entry)
    rewrite_ast(ast)
    renderer = commonmark.HtmlRenderer()

    return ''.join([
        '<article>\n',
        renderer.render(ast),
        '</article>\n'
    ])

def html_for_year_nav_bar(start_year, year, end_year):
    if year > start_year:
        prv = year - 1
        nav = f'    <div>\u2190 <a href="../{prv}/">{prv}</a></div>\n'
    else:
        nav = '    <div></div>\n'

    nav += f'    <h2>{year}</h2>\n'

    if year < end_year:
        nxt = year + 1
        nav += f'    <div><a href="../{nxt}/">{nxt}</a> \u2192</div>\n'
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

    year, week = dt.isocalendar()[0:2]
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
    day_number = split_date(day['date'])[2]
    uri = f'{day_number}.html'
    title = escape(day['title'])
    return f'    <dt>{day_number}</dt><dd><a href="{uri}">{title}</a></dd>\n'

def create_page(path, title, body_html, archive_html, config,
                label, min_year, max_year):
    if min_year == max_year:
        year_range = str(min_year)
    else:
        year_range = f'{min_year}\u2013{max_year}'

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
    html = RE_BODY.sub(lambda x: body_html, html, count=1)
    html = RE_ARCHIVE.sub(archive_html, html)

    Path(config['output-dir']).joinpath(path).write_text(
        html, encoding='utf-8')

    if not config['quiet']:
        print(f"Created '{path}'")

def create_index(days, archive, config, min_year, max_year):
    body_html = ''
    todo = config['days']

    for day in days:
        body_html += html_for_date(
            day['date'], config['date-format'], day['title'], 'archive'
        )
        for entry in day['entries']:
            body_html += html_for_entry(entry)
        todo -= 1
        if not todo:
            break

    archive_html = html_for_archive(
        archive, None, 'archive', config['label-format'])

    create_page(
        'index.html', 'home', body_html, archive_html, config,
        'home', min_year, max_year
    )

def create_year_pages(days, archive, config, min_year, max_year):

    start_year = int((split_date(days[-1]['date']))[0])
    end_year   = int((split_date(days[ 0]['date']))[0])

    archive_html = html_for_archive(archive, None, '..', config['label-format'])

    day_names_row = html_for_day_names_row()
    dt = parse_date(f'{start_year}-01-01')
    it = reversed(days)
    day = next(it)
    date = day['date']
    for year in range(start_year, end_year + 1):
        body_html = ('<div class="tl-topbar"></div>\n<article>\n'
            + html_for_year_nav_bar(start_year, year, end_year))

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

        body_html += '</article>\n'
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

    for year in sorted(years.keys()):
        for month in sorted(years[year].keys()):
            days_for_month = years[year][month]
            first_dt = parse_date(days_for_month[0]['date'])
            month_name = first_dt.strftime('%B')
            nav_bar = html_for_month_nav_bar(years[year], month, month_names)
            body_html = ''.join([
                '<div class="tl-topbar"></div>\n'
                '<article>\n'
                f'  <h2 class="tl-month-year">{month_name} '
                f'<a href="../../{year}/">{year}</a></h2>'
                '  <dl class="tl-days">\n',
                *[html_for_day(day) for day in days_for_month],
                '  </dl>\n',
                nav_bar,
                '</article>\n'
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

    path = f'archive/{year}/week'
    Path(config['output-dir']).joinpath(path).mkdir(
        parents=True, exist_ok=True)
    create_page(
        path + f'/{week}.html',
        title, body_html, archive_html, config,
        title, min_year, max_year
    )

def create_day_and_week_pages(days, archive, config, min_year, max_year):

    week_body_html = ''
    current_year_week = get_year_week(days[0]['date'])
    day_archive_html = html_for_archive(
        archive, None, '../..', config['label-format'])
    index = 0
    for day in days:
        day_body_html = html_for_date(
            day['date'], config['date-format'], day['title'], '../..'
        )
        for entry in day['entries']:
            day_body_html += html_for_entry(entry)

        label = parse_date(day['date']).strftime(config['date-format'])

        year, month, day_number = split_date(day['date'])
        next_prev_html = html_for_next_prev(days, index, config)

        path = f'archive/{year}/{month}'
        Path(config['output-dir']).joinpath(path).mkdir(
            parents=True, exist_ok=True)
        create_page(
            path + f'/{day_number}.html',
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

        index += 1

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

        for entry in page['entries']:
            body_html += html_for_entry(entry)

        create_page(
            f"{page['name']}.html",
            page['title'], body_html, archive_html, config,
            page['label'], min_year, max_year
        )

def get_url_title_description(day, config):

    description = ''
    for entry in day['entries']:
        description += html_for_entry(entry)

    year, month, day_number = split_date(day['date'])
    url = urllib.parse.urljoin(
        config['blog-url'], f'archive/{year}/{month}/{day_number}.html')

    return url, day['title'], description

def get_month_names():

    names = []
    for mon in range(1, 13):
        date = f'2019-{mon:02d}-01'
        names.append(parse_date(date).strftime('%B'))

    return names

def get_end_of_day(date):
    return datetime.strptime(
        f'{date} 23:59:59', '%Y-%m-%d %H:%M:%S').astimezone()

def create_rss_feed(days, config):

    items = []
    todo = config['days']

    for day in days:
        (url, title, description) = get_url_title_description(day, config)

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
        todo -= 1
        if not todo:
            break


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
    todo = config['days']

    for day in days:
        (url, title, description) = get_url_title_description(day, config)

        end_of_day = get_end_of_day(day['date'])
        date_published = str(end_of_day).replace(' ', 'T')

        items.append({
            'id':    url,
            'url':   url,
            'title': title,
            'content_html':   description,
            'date_published': date_published,
        })
        todo -= 1
        if not todo:
            break

    feed = {
        'version':       'https://jsonfeed.org/version/1',
        'title':         config['name'],
        'home_page_url': config['blog-url'],
        'feed_url':      config['json-feed-url'],
        'description':   config['description'],
        'author': {
            'name': config['author']
        },
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

def create_blog(config):
    days, pages = collect_days_and_pages(read_tumblelog_entries(
        config['filename']))

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
        create_rss_feed(days, config)
        create_json_feed(days, config)

    create_pages(pages, archive, config, min_year, max_year)

def create_argument_parser():
    usage = """
  %(prog)s --template-filename TEMPLATE --output-dir HTDOCS
      --author AUTHOR --name BLOGNAME --description DESCRIPTION
      --blog-url URL
      [--days DAYS ] [--css URL] [--date-format DATE] [--min-year YEAR]
      [--quiet] FILE
  %(prog)s --version
  %(prog)s --help"""

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('-t', '--template-filename', dest='template-filename',
                        help='filename of template, required',
                        metavar='TEMPLATE', default=None)
    parser.add_argument('-o', '--output-dir', dest='output-dir',
                        help='directory to store HTML files in, required',
                        metavar='HTDOCS', default=None)
    parser.add_argument('-a', '--author', dest='author',
                        help='author of the blog, required',
                        metavar='AUTHOR', default=None)
    parser.add_argument('-n', '--name', dest='name',
                        help='name of the blog, required',
                        metavar='BLOGNAME', default=None)
    parser.add_argument('--description', dest='description',
                        help='description of the blog, required',
                        metavar='DESCRIPTION', default=None)
    parser.add_argument('-b', '--blog-url', dest='blog-url',
                        help='URL of the blog, required',
                        metavar='URL', default=None)
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
    parser.add_argument('-q', '--quiet', action='store_true', dest='quiet',
                        help="don't show progress", default=False)
    parser.add_argument('-v', '--version', action='store_true', dest='version',
                        help="show version and exit", default=False)
    return parser

def get_config():
    parser = create_argument_parser()
    arguments, args = parser.parse_known_args()
    config = vars(arguments)

    if config['version']:
        print(VERSION)
        sys.exit()

    required = {
        'template-filename':
            'Use --template-filename to specify a template',
        'output-dir':
            'Use --output-dir to specify an output directory for HTML files',
        'author':
            'Use --author to specify an author name',
        'name':
            'Use --name to specify a name for the blog and its feeds',
        'description':
            'Use --description to specify a description of the blog'
            ' and its feeds',
        'blog-url':
            'Use --blog-url to specify the URL of the blog itself',
    }
    for name in sorted(required.keys()):
        if config[name] is None:
            parser.error(required[name])

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
