# tumblelog: a static microblog generator

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

## Python Version Quick Start

Install sass and pip3 for Linux:
```bash
sudo apt install -y git sass python3-pip
```

For macOS:
```bash
brew install sass
brew install pip3
```

Then:
```bash
git clone https://github.com/john-bokma/tumblelog.git
cd tumblelog
python3 -m venv venv
pip3 install commonmark
source venv/bin/activate
mkdir htdocs
sass --sourcemap=none -t compressed styles/steel.scss htdocs/steel.css
python3 tumblelog.py --template-filename tumblelog.html --output-dir htdocs/ \
        --author 'Test' --name 'Test Blog' --description 'This is a test'    \
        --blog-url 'http://example.com/' --css steel.css tumblelog.md
```

To view the generated site at http://localhost:8000/ enter:

```
cd htdocs
python3 -m http.server
```

## Documentation

- Installation of the Perl version: to be written, for now see: [Create a static tumblelog with Perl](http://johnbokma.com/blog/2019/03/30/tumblelog-perl.html)

- [Installation of the Python version](http://johnbokma.com/articles/tumblelog/installation-of-the-python-version-of-tumblelog.html)
- [Testing tumblelog](http://johnbokma.com/articles/tumblelog/testing-tumblelog.html)
- [Getting started](http://johnbokma.com/articles/tumblelog/getting-started-with-tumblelog.html)
- [Using a Makefile](http://johnbokma.com/articles/tumblelog/using-a-makefile.html)
- [Keeping your tumblelog under version control](http://johnbokma.com/articles/tumblelog/keeping-your-blog-under-version-control-with-git.html)

## Style Examples

![A screenshot of the four styles that come with tumblelog](https://repository-images.githubusercontent.com/178557390/30c42f00-e7ae-11e9-839d-d6bd6faa6e48)

A screenshot of four of the twelve styles that come with `tumblelog`.

The `screenshots` directory has 1:1 examples of themes that come with
`tumblelog`.

## Blogs

- [Plurrrr: a tumblelog](http://plurrrr.com/) - by John Bokma

If you want your tumblelog generated site listed, please let me know.
