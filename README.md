# tumblelog: a static microblog generator

## What's New

This project is in active development. Please check the
[CHANGELOG.md](CHANGELOG.md) for what has changed after you have done
a `git pull`.

## About

`tumblelog` is a static microblog generator. There are two versions
available, one written in Perl and one written in Python. Which
version you use is up to you; I make an effort to keep the output of
both versions identical.

The input is a single "Markdown" file divided into pages by starting a
line with a date followed by a title. Each date page can further be
split up into multiple articles using a single % on a line by itself.

Parameters to control the blog are given via command line
arguments. The program creates the blog HTML5 pages and both a JSON
and RSS feed.

## Examples

![A screenshot of the four styles that come with tumblelog](https://repository-images.githubusercontent.com/178557390/b0ba5e80-d991-11e9-9022-c061e713a9ad)

A screenshot of the four styles that come with tumblelog.

The `screenshots` directory has 1:1 examples of themes that come
with `tumblelog`.

## Perl version

Please read my blog entry [Create a static tumblelog with Perl](http://johnbokma.com/blog/2019/03/30/tumblelog-perl.html) which has a thorough explanation on how to use this program. Additionally, read
[a JSON feed for tumblelog](http://johnbokma.com/blog/2019/04/03/a-json-feed-for-tumblelog.html)
for the required additional parameters for the JSON feed.

## Python version

Please read my blog entry [Create a static tumblelog with Python](http://johnbokma.com/blog/2019/04/07/tumblelog-python.html), which
has a thorough explanation on how to use this program.

### Blogs

- [Plurrrr: a tumblelog](http://plurrrr.com/) - by John Bokma

If you want your tumblelog generated site listed, please let me know.
