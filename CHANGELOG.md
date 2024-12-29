# Change Log

## [5.3.5] - 2024-12-29

  - Some small improvements in the Python version
  - Use Unicode names instead of codes in both the Perl and Python version
  - Use better state names in both the Perl and Python version

## [5.3.0] - 2024-12-07

  - Improve regular expressions for heading plus article parsing
  - Bump JSON feed to version 1.1
  - Use application/feed+json MIME type for JSON feed

## [5.2.0] - 2024-11-23

  - Added a Dockerfile for Sass.
  - Added meta name="generator" set to tumblelog plus version number
    to example HTML files.
  - Removed commented out code from tumblelog.py.
  - I now test differently if the OPT_UNSAFE constant is missing.
  - The program now verifies that at least one tag is given if tags are enabled.
  - I now use enumerate() in tumblelog.py (4x)
  - Added notes on images to tumblelog.md and tumblelog-tags.md.
  - Rewrote the README.md almost completely 

## [5.1.3] - 2021-07-12

  - Fixed an issue with a non-existing directory when a year is
    skipped while blogging.

## [5.1.2] - 2021-06-19

  - Improved HTML output to improve CSS styling abilities.
  - Added an optional argument `--feed-size` which controls the number
    of items in each feed. Defaults to 25. Note that the old feed size
    was 14, the same as number of days (`--days` argument).

## [5.0.2] - 2021-06-10

 - Fixed an issue in the Python version of `tumblelog`: using
   `yaml.load(string)` is unsafe, see https://msg.pyyaml.org/load
   for full details.
 - Added experimental Docker files for both the Perl and Python
   version.

## [5.0.1] - 2021-06-10

 - Fixed a minor issue in the Perl version of `tumblelog`.

## [5.0.0] - 2021-06-07

This is a major update which adds tag support to `tumblelog`. Tags are
optional and turned on using the `--tag` option. When on you can
specify the label and title of the tags overview page with the
`--tag-label` argument respectively `--tag-title` argument.

I removed the slogan ("a tumbelog") from the template due to space
restrictions when viewing a generated tumblelog on a small screen; a
tag (which is shown in the label) might push away the slogan resulting
in an odd looking design.

The `description` now includes the `title` of the site.

The CSS style no longer uses `id`s. So `#tl-page` and
`#tl-main-header` are now classes. The reason for this is that ids are
used in link fragments when the `--tags` option is given.

### Migrating to a non-tags version

Migrating to a non-tags version is the easiest:

- Replace 'id="tl-page"' with 'class="tl-page"' and replace
  'id="tl-main-header"' with 'class="tl-main-header"' in your
  template. I recommend to add the title to the description as well,
  see `tumblelog.html`. A diff between your template and the default
  one might help in guiding the required changes.
- If you use your own stylesheet change `#tl-page` and
  `#tl-main-header` into `.tl-page` and `.tl-main-header`.

### Migrating to a tags version (recommended)

See the above steps under *Migrating to a non-tags
version*. Additionally:

  - Each existing and new blog entry must start with a level 2 heading, for
    example: `## A big update to my blog`.
  - Preceding this level 2 header you must specify tags in a YAML
    block. See `tumblelog-tags.md` for examples.
  - If two posts have the same level 2 heading they will have the same
    id. Because ids must be globally unique you can specify an alternative id
    inside the YAML block, for example:

```
---
tags: [example, 'functional programming']
id: not-unique-2
...

## Not Unique
```

  - Tags must be lowercase and space may separate words in a
    tag. Currently a tag is valid lowercase unicode letters or unicode
    digits and a single space is allowed as separator. However, Python
    and Perl seem to disagree on the set of codepoints this
    entails. So if you ever switch from the Perl to the Python version
    or vice versa you might get an error about an invalid tag.

    Note that in the above example the tag *functional programming* is
    between single quotes. This is just cosmetic; you can leave them
    out.

If you have any questions or encounter any issues feel free to contact
me at contact@johnbokma.com.

## [4.1.0] - 2020-10-17

  - Fixed calendar bug
  - Cleaned up the code after (Perl::Critic for Perl version, pylint
    for Python version)
  - Refactored styles and cleaned up (stylelint)
  - Bump version to 4.1.0

## [4.0.6] - 2020-08-14

  - Changed padding-left for ordered and unordered lists to be smaller
  - Bump version to 4.0.6

## [4.0.5] - 2020-07-25

  - Fixed spelling of "San Francisco" in SCSS files, thanks *Hacker
    News* user
    [JustARandomGuy](https://news.ycombinator.com/user?id=JustARandomGuy)
    for spotting this
  - Fixed copyright and license in SCSS files
  - Bump version to 4.0.5

## [4.0.4] - 2020-07-22

  - Change license to MIT; add LICENSE file
  - Bump version to 4.0.4

## [4.0.3] - 2019-02-22

  - In the year overview show the year centered (use grid instead of
    flex)
  - Bump version to 4.0.3

## [4.0.2] - 2019-11-02

Bug fix:

  - Perl: drop empty entries just like the Python version

## [4.0.1] - 2019-11-02

Bug fix:

  - Python: split file into entries if and only if a line starts with
    a single `%` character.

## [4.0.0] - 2019-10-25

Adds support for year overview pages (calendar) and month overview
pages for active months.

Blog entry and page entry titles are now *mandatory*. This to make
the month overview pages look better.

Bug fixes:

 - Both: pubDate for RSS feed is now always USA locale (required)
 - Python: locale is honored
 - Perl: Time::Piece strftime is properly UTF-8 encoded (bug in Time::Piece)

## [3.0.2] - 2019-10-12

Provides the argument `--min-year` to specify the minimum year to be
used in the copyright notice.

## [3.0.1] - 2019-10-11

Calculates the maximum year for copyright from the current local time.

## [3.0.0] - 2019-10-05

This version adds the ability to create non-blog pages, for example an *about* page, and a *subscription page*. It should even be possible to create a micro site this way, without a blog. The syntax for the non-blog page marker is as follows:

```
@PAGE[LABEL] YYYY-MM-DD TITLE
```

With:

 - PAGE - the filename of the page without the `.html` extension
 - LABEL - the label of the page
 - YYYY-MM-DD - the date the page was updated
 - TITLE - The title of the page

For example:

```
@subscribe[subscribe] 2019-10-05 Subscribe
```

If the date is immediately followed by an exclamation mark the date is also shown on the generated HTML page.

Page titels are no longer generated by gluing the blog name and the title together; if you want the blog name in the HTML you have to add it to the template. For example:

```
    <title>[% title %] — [% name %]</title>
```

Instead of:

```
    <title>[% title %]</title>
```

## [2.5.0] - 2019-10-02

Add an RSS feed

 - Add description option (required)
 - Deprecate `feed-url` template variable
 - Add `rss-feed-url`, `json-feed-url`, and `description` template variables

## [2.1.1] - 2019-09-26

The file _tumblelog.scss has been slightly reorganised.

## [2.1.0] - 2019-09-24

This update removes one "nav element with no heading" remark in the W3C
Markup Validation Service in outline mode.

Note that this means that you have to change the template you use for your blog and maybe the CSS if you modified `_tumblelog.scss`.

See [Nav Element with no Heading](http://johnbokma.com/blog/2019/09/24/nav-element-with-no-heading.html) for an explanation and what to change in your template.

## [2.0.1] - 2019-09-18

It turned out that version 2.0.0 of tumblelog has a small bug: if you use an older version of the CommonMark Perl module the constant OPT_UNSAFE is not defined. So I added some code that checks if this constant exists and if not adds it.

## [2.0.0] - 2019-09-17

Note that images with text following immediately are rendered as a
figure with the text in a figcaption element. This means that:

```
![Alt text](cat.jpg)
Photo of a cat.
```

is rendered as HTML as follows:

```
<figure>
<img alt="Alt text" src="cat.jpg" />
<figcaption>
Photo of a cat.
</figcaption>
</figure>
```

This allows for CSS styling of both the image and the caption.

## Older

### Twitter Card and Facebook Sharing support

New: support has been added for Twitter Card and Facebook Sharing, see
[Adding Twitter Card and Facebook Sharing support to Tumblelog - John
Bokma](http://johnbokma.com/blog/2019/08/11/adding-twitter-card-and-facebook-sharing-support-to-tumblelog.html)
for more information.

### SEO friendly titles

New: You can now specify a title after the ISO 8601 date which is
assigned to the `title` element of the day page, see [SEO friendly titles for tumblelog](http://johnbokma.com/blog/2019/04/12/seo-friendly-titles-for-tumblelog.html).
