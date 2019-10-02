# Change Log

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
