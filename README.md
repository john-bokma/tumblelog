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

For example:

```
perl tumblelog.pl --template-filename tumblelog.html --output-dir htdocs/ \
     --author 'Your Name' --name 'Your Blog' --description 'Your Description' \
     --blog-url 'http://example.com/' --css soothe.css tumblelog.md
```

If you have Python 3 installed you can run a simple webserver inside
`htdocs` and view the generated site by entering
http://localhost:8000/ in your browser:

```
python3 -m http.server
```

## Style Examples

![A screenshot of the four styles that come with tumblelog](https://repository-images.githubusercontent.com/178557390/30c42f00-e7ae-11e9-839d-d6bd6faa6e48)

A screenshot of four of the seven styles that come with `tumblelog`.

The `screenshots` directory has 1:1 examples of themes that come
with `tumblelog`.

## Perl Version

Please read my blog entry [Create a static tumblelog with Perl](http://johnbokma.com/blog/2019/03/30/tumblelog-perl.html) which has a thorough explanation on how to use this program. Additionally, read
[a JSON feed for tumblelog](http://johnbokma.com/blog/2019/04/03/a-json-feed-for-tumblelog.html)
for the required additional parameters for the JSON feed.

## Python Version

Please read my blog entry [Create a static tumblelog with Python](http://johnbokma.com/blog/2019/04/07/tumblelog-python.html), which
has a thorough explanation on how to use this program.

## Roadmap

### Later This Month

 - Calendar view to make it easy to browse to a specific date.

## Blogs

- [Plurrrr: a tumblelog](http://plurrrr.com/) - by John Bokma

If you want your tumblelog generated site listed, please let me know.
