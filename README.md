# tumblelog: a static microblog generator

## New in version 2.0.0

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

## Perl version

Please read my blog entry [Create a static tumblelog with Perl](http://johnbokma.com/blog/2019/03/30/tumblelog-perl.html) which has a thorough explanation on how to use this program. Additionally, read
[a JSON feed for tumblelog](http://johnbokma.com/blog/2019/04/03/a-json-feed-for-tumblelog.html)
for the required additional parameters for the JSON feed.

## Python version

Please read my blog entry [Create a static tumblelog with Python](http://johnbokma.com/blog/2019/04/07/tumblelog-python.html), which
has a thorough explanation on how to use this program.

## SEO friendly titles

New: You can now specify a title after the ISO 8601 date which is
assigned to the `title` element of the day page, see [SEO friendly titles for tumblelog](http://johnbokma.com/blog/2019/04/12/seo-friendly-titles-for-tumblelog.html).

## Twitter Card and Facebook Sharing support

New: support has been added for Twitter Card and Facebook Sharing, see
[Adding Twitter Card and Facebook Sharing support to Tumblelog - John
Bokma](http://johnbokma.com/blog/2019/08/11/adding-twitter-card-and-facebook-sharing-support-to-tumblelog.html)
for more information.

## Examples

![A screenshot of the four styles that come with tumblelog](https://repository-images.githubusercontent.com/178557390/b0ba5e80-d991-11e9-9022-c061e713a9ad)

A screenshot of the four styles that come with tumblelog.

The `screenshots` directory has 1:1 examples of themes that come
with `tumblelog`.

### Blogs

- [Plurrrr: a tumblelog](http://plurrrr.com/) - by John Bokma

If you want your tumblelog generated site listed, please let me know.
