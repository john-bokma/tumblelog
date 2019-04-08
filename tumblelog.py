#!/usr/bin/env python3
#
# (c) John Bokma, 2019
#
# This program is free software; you can redistribute it and/or modify it
# under the same terms as Python itself.

import re
import json
from html import escape
import urllib.parse
from pathlib import Path
from optparse import OptionParser
from datetime import datetime
from collections import defaultdict, deque
from commonmark import commonmark


RE_YEAR_RANGE = r'(?x) \[% \s+ year-range \s+ %\]'
RE_LABEL      = r'(?x) \[% \s+ label      \s+ %\]'
RE_CSS        = r'(?x) \[% \s+ css        \s+ %\]'
RE_NAME       = r'(?x) \[% \s+ name       \s+ %\]'
RE_AUTHOR     = r'(?x) \[% \s+ author     \s+ %\]'
RE_FEED_URL   = r'(?x) \[% \s+ feed-url   \s+ %\]'
RE_BODY       = r'(?x) \[% \s+ body       \s+ %\] \n'
RE_ARCHIVE    = r'(?x) \[% \s+ archive    \s+ %\] \n'


class NoEntriesError(Exception):
    """Thrown in case there are no blog entries; the file is empty"""

class NoDateSpecified(Exception):
    """Thrown in case the first blog entry has no date"""


def join_year_week(year, week):
    return f'{year}-{week}'

def split_year_week(year_week):
    return year_week.split('-')

def parse_date(str):
    return datetime.strptime(str, '%Y-%m-%d')

def read_tumblelog_entries(filename):
    with open(filename, encoding='utf8') as f:
        entries = [item for item in f.read().split('%\n') if item]
    if not entries:
        raise NoEntriesError('No blog entries found')

    return entries

def collect_daily_entries(entries):
    pattern = re.compile('(\d{4}-\d{2}-\d{2})\n(.*)', flags=re.DOTALL)
    date = None
    collected = defaultdict(list)

    for entry in entries:
        match = pattern.match(entry)
        if match:
            date = match.group(1)
            entry = match.group(2)
        if date is None:
            raise NoDateSpecified('No date specified for first tumblelog entry')
        collected[date].append(entry)

    return collected

def collect_weekly_entries(entries):
    collected = defaultdict(dict)
    dates = sorted(entries.keys(), reverse=True)

    for date in dates:
        dt = parse_date(date)
        year_week = join_year_week(*dt.isocalendar()[0:2])
        collected[year_week][date] = entries[date]

    return collected

def create_archive(year_weeks):
    archive = defaultdict(deque)
    for year_week in year_weeks:
        year, week = split_year_week( year_week )
        archive[year].appendleft(week)

    return archive

def html_for_archive(archive, current_year_week, path):
    html = '<nav>\n  <dl class="tl-archive">\n'
    for year in sorted(archive.keys(), reverse=True):
        html += f'    <dt>{year}</dt>\n    <dd>\n      <ul>\n'
        for week in archive[year]:
            year_week = join_year_week(year, week)
            if current_year_week is not None and year_week == current_year_week:
                html += f'        <li class="tl-self">{week}</li>\n'
            else:
                uri = f'{path}/{year}/week/{week}.html'
                html += ''.join([
                    '        <li>',
                    f'<a href="{uri}" title="{year_week}">{week}</a></li>\n'
                ])
        html += '      </ul>\n    </dd>\n'
    html += '  </dl>\n</nav>\n'

    return html

def html_for_date(date, date_format, path):
    year, month, day = date.split('-')
    uri = f'{path}/{year}/{month}/{day}.html'

    return ''.join([
        f'<time class="tl-date" datetime="{date}"><a href="{uri}">',
        parse_date(date).strftime(date_format),
        '</a></time>\n'
    ])

def html_for_entry(entry):
    return ''.join([
        '<article>\n',
        commonmark(entry),
        '</article>\n'
    ])

def create_page(path, body_html, archive_html, options,
                label, min_year, max_year):
    year_range = min_year if min_year == max_year else f'{min-year}-{max_year}'

    slashes = path.count('/')
    css = ''.join(['../' * slashes, options['css']])

    html = options['template']
    html = re.sub(RE_YEAR_RANGE, year_range, html)
    html = re.sub(RE_LABEL,      escape(label), html)
    html = re.sub(RE_CSS,        css, html)
    html = re.sub(RE_NAME,       escape(options['name']), html)
    html = re.sub(RE_AUTHOR,     escape(options['author']), html)
    html = re.sub(RE_FEED_URL,   options['feed-url'], html)
    html = re.sub(RE_BODY,       lambda x: body_html, html, count=1)
    html = re.sub(RE_ARCHIVE,    archive_html, html)

    Path(options['output-dir']).joinpath(path).write_text(
        html, encoding='utf-8')

    if not options['quiet']:
        print(f"Created '{path}'")

def create_index(year_weeks, collected, archive, options, min_year, max_year):
    body_html = ''
    todo = options['days']
    for year_week in year_weeks:
        dates = sorted(collected[year_week], reverse=True)
        for date in dates:
            body_html += html_for_date(
                date, options['date-format'], 'archive'
            )
            for entry in collected[year_week][date]:
                body_html += html_for_entry(entry)
            todo -= 1
            if not todo:
                break
        else:
            continue
        break

    archive_html = html_for_archive(archive, None, 'archive')

    Path(options['output-dir']).mkdir(parents=True, exist_ok=True)
    create_page(
        'index.html', body_html, archive_html, options,
        'home', min_year, max_year
    )

def create_other_pages(
        year_week, collected, archive, options, min_year, max_year):

    week_body_html = ''
    dates = sorted(collected[year_week], reverse=True)
    for date in dates:
        day_body_html = html_for_date(
            date, options['date-format'], '../..'
        )
        for entry in collected[year_week][date]:
            day_body_html += html_for_entry(entry)

        archive_html = html_for_archive(archive, None, '../..')

        year, month, day = date.split('-')
        path = f'archive/{year}/{month}'
        Path(options['output-dir']).joinpath(path).mkdir(
            parents=True, exist_ok=True)
        create_page(
            path + f'/{day}.html',
            day_body_html, archive_html, options,
            parse_date( date ).strftime(options['date-format']),
            min_year, max_year
        )

        week_body_html += day_body_html

    archive_html = html_for_archive(archive, year_week, '../..')

    year, week = split_year_week(year_week)
    path = f'archive/{year}/week'
    Path(options['output-dir']).joinpath(path).mkdir(
        parents=True, exist_ok=True)
    create_page(
        path + f'/{week}.html',
        week_body_html, archive_html, options,
        f'week {week}, {year}', min_year, max_year
    )

def create_json_feed(year_weeks, collected, options):
    items = []
    todo = options['days']
    for year_week in year_weeks:
        dates = sorted(collected[year_week], reverse=True)
        for date in dates:
            html = ''
            for entry in collected[year_week][date]:
                html += html_for_entry(entry)

            year, month, day = date.split('-')
            url = urllib.parse.urljoin(
                options['blog-url'], f'archive/{year}/{month}/{day}.html')
            title = parse_date(date).strftime(options['date-format'])
            items.append({
                'id':    url,
                'url':   url,
                'title': title,
                'content_html':   html,
                'date_published': date
            })

            todo -= 1
            if not todo:
                break
        else:
            continue
        break

    feed = {
        'version':       'https://jsonfeed.org/version/1',
        'title':         options['name'],
        'home_page_url': options['blog-url'],
        'feed_url':      options['feed-url'],
        'author': {
            'name': options['author']
        },
        'items': items
    }
    path = options['feed-path']
    p = Path(options['output-dir']).joinpath(path)
    with p.open(mode='w', encoding='utf-8') as f:
        json.dump(feed, f, indent=3, ensure_ascii=False, sort_keys=True,
            separators=(',', ': '))
        print('', file=f)

    if not options['quiet']:
        print(f"Created '{path}'")

def create_blog(options):
    collected = collect_weekly_entries(
        collect_daily_entries(
            read_tumblelog_entries(options['filename'])
        )
    )

    year_weeks = sorted(collected.keys(), reverse=True)
    max_year = split_year_week(year_weeks[0])[0]
    min_year = split_year_week(year_weeks[-1])[0]

    archive = create_archive(year_weeks)

    create_index(year_weeks, collected, archive, options, min_year, max_year)
    for year_week in year_weeks:
        create_other_pages(
            year_week, collected, archive, options, min_year, max_year)

    create_json_feed(year_weeks, collected, options)

def create_option_parser():
    usage = """
  %prog --template-filename TEMPLATE --output-dir HTDOCS
      --author AUTHOR -name BLOGNAME --blog-url URL
      [--days DAYS ] [--css URL] [--date-format DATE] [--quiet] FILE
  %prog --help"""

    parser = OptionParser(usage=usage)
    parser.add_option('-t', '--template-filename', dest='template-filename',
                      help='filename of template, required',
                      metavar='TEMPLATE', default=None)
    parser.add_option('-o', '--output-dir', dest='output-dir',
                      help='directory to store HTML files in, required',
                      metavar='HTDOCS', default=None)
    parser.add_option('-a', '--author', dest='author',
                      help='author of the blog, required',
                      metavar='AUTHOR', default=None)
    parser.add_option('-n', '--name', dest='name',
                      help='name of the blog, required',
                      metavar='BLOGNAME', default=None)
    parser.add_option('-b', '--blog-url', dest='blog-url',
                      help='URL of the blog, required',
                      metavar='URL', default=None)
    parser.add_option('-d', '--days', dest='days',
                      help='number of days to show on the index; default 14',
                      metavar='DAYS', type='int', default=14)
    parser.add_option('-c', '--css', dest='css',
                      help='URL of the stylesheet to use; default styles.css',
                      metavar='URL', default='styles.css')
    parser.add_option('--date-format', dest='date-format',
                      help='how to format the date; default %d %b %Y',
                      metavar='FORMAT', default='%d %b %Y')
    parser.add_option('-q', '--quiet', action='store_true', dest='quiet',
                      help="don't show progress", default=False)

    return parser

def get_options():
    parser = create_option_parser()
    options, args = parser.parse_args()
    options_dict = vars(options)

    required = {
        'template-filename':
            'Use --template-filename to specify a template',
        'output-dir':
            'Use --output-dir to specify an output directory for HTML files',
        'author':
            'Use --author to specify an author name',
        'name':
            'Use --name to specify a name for the blog and its feed',
        'blog-url':
            'Use --blog-url to specify the URL of the blog itself',
    }
    for name in sorted(required.keys()):
        if options_dict[name] is None:
            parser.error(required[name])

    if len(args) == 0:
        parser.error('Specify a filename that contains the blog entries')
    if len(args) > 1:
        print('Additional arguments have been skipped', file=sys.stderr)

    options_dict['filename'] = args[0]
    with open(options_dict['template-filename'], encoding='utf-8') as f:
        options_dict['template'] = f.read()

    options_dict['feed-path'] = 'feed.json'
    options_dict['feed-url'] = urllib.parse.urljoin(
        options_dict['blog-url'], options_dict['feed-path'])

    return options_dict

create_blog(get_options())
