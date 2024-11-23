# tumblelog: a static microblog generator

`tumblelog` is a static microblog generator. There are two versions
available, one written in Perl and one written in Python. Which
version you use is up to you; I make an effort to keep the output of
both versions identical except for minor differences between the
render libraries used.

The input is a single Markdown file with additional directives to
define pages and, optionally, tags.

Parameters to control the blog are given via command line
arguments. Use the `--help` argument to get an overview of all
possible arguments. The `tumblelog` program creates the blog HTML5
pages and both a [JSON
feed](http://johnbokma.com/blog/2019/04/03/a-json-feed-for-tumblelog.html)
and an RSS feed.

See for an example my personal microblog
[Plurrrr](https://plurrrr.com/). For an example with images, see blog
article [The International Mineral
Fair](https://plurrrr.com/archive/2023/03/26.html#the-international-mineral-fair).

Generation of HTML is fast. On my outdated Mac Mini Late 2014 it takes
a little over 30 seconds to generate 2600+ HTML files out of 1600+ day
entries using the Python version in Docker.

The instructions in this README assume the following directory layout:

```
   `--- projects
   |       :
   |       `--- tumblelog
   |       :       :
   |       :       `--- screenshots
   |               `--- styles
   |               :
   |
   `--- sites
           :
           `--- example.com
           :       :
           :       `--- htdocs
```

Check out the `tumblelog` project in the `projects` directory as follows:

```bash
cd projects
sudo apt install -y git
git clone https://github.com/john-bokma/tumblelog.git
```

You can view the generated HTML pages if you have Python installed on
your system by entering inside the `htdocs` directory either:

```bash
python3 -m http.server
```

for Python 3 or for Python 2:

```bash
python -m SimpleHTTPServer 8000
```

Next, open http://localhost:8000/ to view your pages. Note that not
all links work if you generated the site for your own domain and view
it via a local webserver.

![A screenshot of the four styles that come with tumblelog](https://repository-images.githubusercontent.com/178557390/30c42f00-e7ae-11e9-839d-d6bd6faa6e48)

A screenshot of four of the thirteen styles that come with `tumblelog`.

The `screenshots` directory has 1:1 examples of themes that come with
`tumblelog`.

**Note**: `tumblelog` uses quite some arguments in order to work. I
recommend [using a Makefile](http://johnbokma.com/articles/tumblelog/using-a-makefile.html) to make life easier.

## Getting started using Docker

If you're already using Docker it's probably the easiest way to start
with `tumblelog`.

### Creating the style sheet

The `tumblelog` project comes with several styles written in
[Sass](https://sass-lang.com/). You can convert such a style to CSS
using the Sass container.

First, create the container image as follows. You must be inside the
`tumblelog` directory.

```bash
docker build --tag node/sass -f sass.Dockerfile .
```

Next, change to the directory that contains your `htdocs`
directory. In the example layout given earlier this is `example.com`
inside the `sites` directory.

Next, select a style, except the ones starting with an underscore, you
want to convert to CSS from the `styles` directory. You can see
examples of each style in the `screenshots` directory. For example
use `steel.scss`:

```bash
docker run --rm \
       --volume "`pwd`/../../projects/tumblelog/styles:/data/styles:ro" \
       --volume "`pwd`/htdocs:/data/htdocs" \
       --user `id -u`:`id -g` node/sass --no-source-map --style compressed \
       --silence-deprecation import \
       styles/steel.scss htdocs/steel.css
```

This should create a file named `steel.css` inside your `htdocs`
directory.

**Note**: I silence the deprecation regarding the use of `@import`. I
will modify the Sass files soon in order to fix this issue.

For more information regarding the Sass container see: [A Docker Image
for Sass](http://johnbokma.com/blog/2021/06/17/a-docker-image-for-sass.html).

### Running the Python version

First, create the container image as follows. You must be inside the
`tumblelog` directory.

```bash
docker build --tag tumblelog/python -f python.Dockerfile .
```

Next, you need an input file. In this example we create a tumblelog
with tags so copy from inside the `tumblelog` directory the file
`tumblelog-tags.html` to your site, in this case `example.com` as
follows:

```bash
cp tumblelog-tags.md ../../sites/example.com/example.md
```

Next, also copy the template file as follows:

```bash
cp tumblelog-tags.html ../../sites/example.com/example.html

```

Next, to run the container (version with tags) you must be located
inside your site's directory. In this case `example.com`:

```bash
cd ../../sites/example.com
docker run --rm --volume "`pwd`:/data" --user `id -u`:`id -g` \
       -e TZ="Europe/Amsterdam" \
       tumblelog/python --template-filename example.html \
       --output-dir htdocs/ \
       --author 'Test' --name 'Test Blog' --description 'This is a test' \
       --blog-url 'http://example.com/' --css steel.css --tags \
       example.md
```

*Note*: make sure you use your own time zone, see for more
information: [Timezones in Alpine Docker
Containers](http://johnbokma.com/blog/2021/06/14/timezones-in-alpine-docker-containers.html).

### Running the Perl version

First, create the container image as follows. You must be inside the
`tumblelog` directory.

```bash
docker build --tag tumblelog/perl -f perl.Dockerfile .
```

Next, you need an input file. In this example we create a tumblelog
with tags so copy from inside the `tumblelog` directory the file
`tumblelog-tags.html` to your site, in this case `example.com` as
follows:

```bash
cp tumblelog-tags.md ../../sites/example.com/example.md
```

Next, also copy the template file as follows:

```bash
cp tumblelog-tags.html ../../sites/example.com/example.html

```

Next, to run the container (version with tags) you must be located
inside your site's directory. In this case `example.com`:

```bash
cd ../../sites/example.com
docker run --rm --volume "`pwd`:/data" --user `id -u`:`id -g` \
       -e TZ="Europe/Amsterdam" \
       tumblelog/perl --template-filename example.html \
       --output-dir htdocs/ \
       --author 'Test' --name 'Test Blog' --description 'This is a test' \
       --blog-url 'http://example.com/' --css steel.css --tags \
       example.md
```

*Note*: make sure you use your own time zone, see for more
information: [Timezones in Alpine Docker
Containers](http://johnbokma.com/blog/2021/06/14/timezones-in-alpine-docker-containers.html).

## Python Version Quick Start

Install sass and pip3 for Linux:
```bash
sudo apt install -y git sass python3-pip
```

Or for macOS:
```bash
brew install sass
brew install pip3
```

Then inside the `tumblelog` directory:
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

**Note**: You can leave the virtual environment later on using `deactivate`.

Next, change to the directory that contains your `htdocs`
directory. In the example layout given earlier this is `example.com`
inside the `sites` directory.

Next, select a style, except the ones starting with an underscore, you
want to convert to CSS from the `styles` directory. You can see
examples of each style in the `screenshots` directory. For example
use `steel.scss`:

```bash
sass --sourcemap=none -t compressed \
     ../../projects/tumblelog/styles/steel.scss htdocs/steel.css
```

This should create a file named `steel.css` inside your `htdocs`
directory.

Next, you need an input file. In this example we create a tumblelog
with tags so copy from inside the `tumblelog` directory the file
`tumblelog-tags.html` to your site, in this case `example.com` as
follows:

```bash
cp ../../projects/tumblelog/tumblelog-tags.md example.md
```

Next, also copy the template file as follows:

```bash
cp ../../projects/tumblelog/tumblelog-tags.html example.html

```

Next run the Python program (version with tags) inside the
`example.com` directory as follows:

```
python3 ../../projects/tumblelog/tumblelog.py
        --template-filename example.html \
        --output-dir htdocs/ \
        --author 'Test' --name 'Test Blog' --description 'This is a test' \
        --blog-url 'http://example.com/' --css steel.css --tags \
        example.md
```

## Documentation

- Installation of the Perl version: to be written, for now see: [Getting started with the Perl version of tumblelog on Ubuntu 18.04 LTS](http://johnbokma.com/blog/2020/03/28/perl-version-tumblelog-ubuntu-bionic-beaver-howto.html)

- [Installation of the Python version](http://johnbokma.com/articles/tumblelog/installation-of-the-python-version-of-tumblelog.html)
- [Testing tumblelog](http://johnbokma.com/articles/tumblelog/testing-tumblelog.html)
- [Getting started](http://johnbokma.com/articles/tumblelog/getting-started-with-tumblelog.html)
- [Using a Makefile](http://johnbokma.com/articles/tumblelog/using-a-makefile.html)
- [Keeping your tumblelog under version control](http://johnbokma.com/articles/tumblelog/keeping-your-blog-under-version-control-with-git.html)


## Blogs

- [Plurrrr: a tumblelog](http://plurrrr.com/) - by John Bokma

If you want your tumblelog generated site listed here, please let me know.
