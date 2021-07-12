#!/usr/bin/perl

use strict;
use warnings;
use open ':std', ':encoding(UTF-8)';

use URI;
use JSON::XS;
use YAML::XS;
use Path::Tiny;
use CommonMark qw(:opt :node :event);
use Time::Piece;
use Time::Seconds;
use Getopt::Long;
use List::Util 'min';
use Encode 'decode';
use Try::Tiny;

my $VERSION = '5.1.3';

my $RE_DATE_TITLE    = qr/^(\d{4}-\d{2}-\d{2})(.*?)\n(.*)/s;
my $RE_AT_PAGE_TITLE =
    qr/^@([a-z0-9_-]+)\[(.+)\]\s+(\d{4}-\d{2}-\d{2})(!?)(.*?)\n(.*)/s;
my $RE_YAML_MARKDOWN = qr/\s*(---\n.*?\.\.\.\n)?(.*)/sm;
my $RE_TAG           = qr/^[\p{Ll}\d]+(?: [\p{Ll}\d]+)*$/;

my $RE_TITLE         = qr/\[% \s* title         \s* %\]/x;
my $RE_YEAR_RANGE    = qr/\[% \s* year-range    \s* %\]/x;
my $RE_LABEL         = qr/\[% \s* label         \s* %\]/x;
my $RE_CSS           = qr/\[% \s* css           \s* %\]/x;
my $RE_NAME          = qr/\[% \s* name          \s* %\]/x;
my $RE_AUTHOR        = qr/\[% \s* author        \s* %\]/x;
my $RE_DESCRIPTION   = qr/\[% \s* description   \s* %\]/x;
my $RE_VERSION       = qr/\[% \s* version       \s* %\]/x;
my $RE_PAGE_URL      = qr/\[% \s* page-url      \s* %\]/x;
my $RE_RSS_FEED_URL  = qr/\[% \s* rss-feed-url  \s* %\]/x;
my $RE_JSON_FEED_URL = qr/\[% \s* json-feed-url \s* %\]/x;
my $RE_BODY          = qr/\[% \s* body          \s* %\] \n/x;
my $RE_ARCHIVE       = qr/\[% \s* archive       \s* %\] \n/x;

my @MON_LIST = qw( Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec );
my @DAY_LIST = qw( Sun Mon Tue Wed Thu Fri Sat );

BEGIN {
    # An older version of CommonMark hasn't got this constant yet, so
    # we can safely set it to 0
    unless ( main->can( 'OPT_UNSAFE' ) ) {
        eval 'sub OPT_UNSAFE { return 0 }';
    }
}

create_blog( get_config() );

sub get_config {

    my %arguments = (
        'template-filename' => undef,
        'output-dir'        => undef,
        'author'            => undef,
        'name'              => undef,
        'description'       => undef,
        'blog-url'          => undef,
        'days'              => 14,
        'css'               => 'styles.css',
        'date-format'       => '%d %b %Y',
        'label-format'      => 'week %V, %Y',
        'min-year'          => undef,
        'tags'              => 0,
        'tags-label'        => 'tags',
        'tags-title'        => 'Tags',
        'feed-size'         => 25,
        'quiet'             => 0,
        'version'           => 0,
        'help'              => 0,
    );

    GetOptions(
        \%arguments,
        'template-filename=s',
        'output-dir=s',
        'author=s',
        'name=s',
        'description=s',
        'blog-url=s',
        'days=i',
        'css=s',
        'date-format=s',
        'label-format=s',
        'min-year=i',
        'tags',
        'tags-label=s',
        'tags-title=s',
        'feed-size=i',
        'quiet',
        'version',
        'help',
    );

    show_usage_and_exit() if $arguments{ help };

    if ( $arguments{ version } ) {
        print "$VERSION\n";
        exit;
    }

    my $missing = 0;
    my %required = (
        'template-filename' =>
            'Use --template-filename to specify a template',
        'output-dir' =>
            'Use --output-dir to specify an output directory for HTML files',
        'author' =>
            'Use --author to specify an author name',
        'name' =>
            'Use --name to specify a name for the blog and its feeds',
        'description' =>
            'Use --description to specify a description of the blog'
            .' and its feeds',
        'blog-url' =>
            'Use --blog-url to specify the URL of the blog itself',
    );
    for my $name ( sort keys %required ) {
        if ( !defined $arguments{ $name } ) {
            warn "$required{ $name }\n";
            $missing++;
        }
    }
    show_usage_and_exit( 2 ) if $missing;

    my $filename = shift @ARGV;
    if ( !defined $filename ) {
        warn "Specify a filename that contains the entries\n";
        show_usage_and_exit(1);
    }
    warn "Additional arguments have been skipped\n" if @ARGV;

    my %config = %arguments;
    $config{ filename } = $filename;
    $config{ template } = path( $config{ 'template-filename' } )
        ->slurp_utf8();
    $config{ 'json-path' } = 'feed.json';
    $config{ 'json-feed-url' } = URI->new_abs(
        @config{ qw( json-path blog-url ) }
    )->as_string();
    $config{ 'rss-path' } = 'feed.rss';
    $config{ 'rss-feed-url' } = URI->new_abs(
        @config{ qw( rss-path blog-url ) }
    )->as_string();

    return \%config;
}

sub create_blog {

    my $config = shift;

    my ( $days, $pages ) = collect_days_and_pages(
        read_entries( $config->{ filename } )
    );

    if ( $config->{ tags } ) {
        convert_articles_with_metablock_to_html( $days, $config );
    }
    else {
        convert_articles_to_html( $days );
    }
    convert_articles_to_html( $pages );

    my $max_year = ( localtime() )[ 5 ] + 1900; # current year
    my $min_year;
    if ( defined $config->{ 'min-year' } ) {
        $min_year = $config->{ 'min-year' };
    }
    else {
        $min_year = $max_year;
        $min_year = min(
            $min_year, ( split_date( $days->[ -1 ]{ date } ) )[ 0 ]
        ) if @$days;

        $min_year = min(
            $min_year, ( split_date( $pages->[ -1 ]{ date } ) )[ 0 ]
        ) if @$pages;
    }

    path( $config->{ 'output-dir' } )->mkpath();

    my $archive = create_archive( $days );
    if ( @$days ) {
        create_index( $days, $archive, $config, $min_year, $max_year );

        create_day_and_week_pages(
            $days, $archive, $config, $min_year, $max_year
        );

        create_month_pages(
            $days, $archive, $config, $min_year, $max_year
        );

        create_year_pages(
            $days, $archive, $config, $min_year, $max_year
        );

        create_tag_pages(
            $days, $archive, $config, $min_year, $max_year
        ) if $config->{tags};

        create_rss_feed( $days, $config );
        create_json_feed( $days, $config );
    }

    create_pages( $pages, $archive, $config, $min_year, $max_year );

    return;
}

sub create_index {

    my ( $days, $archive, $config, $min_year, $max_year ) = @_;

    my $body_html;
    my $todo = $config->{ days };

    for my $day ( @$days ) {

        $body_html .= html_for_date(
            $day->{ date }, $config->{ 'date-format' }, $day->{ title },
            'archive'
        ) . join( '', map { $_->{ html } } @{ $day->{ articles } } );

        --$todo or last;
    }

    my $archive_html = html_for_archive(
        $archive, undef, 'archive', $config->{ 'label-format' }
    );

    create_page(
        'index.html', 'home', $body_html, $archive_html, $config,
        'home', $min_year, $max_year
    );

    return;
}

sub create_day_and_week_pages {

    my ( $days, $archive, $config, $min_year, $max_year ) = @_;

    my $year_week;
    my $week_body_html;
    my $current_year_week = get_year_week( $days->[ 0 ]{ date } );
    my $day_archive_html = html_for_archive(
        $archive, undef, '../..', $config->{ 'label-format' }
    );
    my $index = 0;
    for my $day ( @$days ) {

        my $day_body_html = html_for_date(
            $day->{ date }, $config->{ 'date-format' }, $day->{ title },
            '../..'
        ) . join( '', map { $_->{ html } } @{ $day->{ articles } } );

        my $label = decode_utf8( parse_date( $day->{ date } )
            ->strftime( $config->{ 'date-format' } ) );

        my ( $year, $month, $day_number ) = split_date( $day->{ date } );
        my $next_prev_html = html_for_next_prev( $days, $index, $config );

        path( "$config->{ 'output-dir' }/archive/$year/$month")->mkpath();
        create_page(
            "archive/$year/$month/$day_number.html",
            $day->{ title }, $day_body_html . $next_prev_html,
            $day_archive_html,
            $config,
            $label, $min_year, $max_year
        );

        $year_week = get_year_week( $day->{ date } );
        if ( $year_week eq $current_year_week ) {
            $week_body_html .= $day_body_html;
        }
        else {
            create_week_page(
                $current_year_week, $week_body_html, $archive, $config,
                $min_year, $max_year
            );
            $current_year_week = $year_week;
            $week_body_html = $day_body_html;
        }
        $index++;
    }

    create_week_page(
        $year_week, $week_body_html, $archive, $config,
        $min_year, $max_year
    );

    return;
}

sub create_pages {

    my ( $pages, $archive, $config, $min_year, $max_year ) = @_;

    my $archive_html = %$archive ? html_for_archive(
        $archive, undef, 'archive', $config->{ 'label-format' }
    ) : '';

    for my $page ( @$pages ) {
        my $date = $page->{ date };
        my $link_text = escape(
            decode_utf8(
                parse_date( $date )->strftime( $config->{ 'date-format' } )
            )
        );
        my $body_html;
        if ( $page->{ 'show-date' } ) {
            $body_html  = qq(<time class="tl-date" datetime="$date">)
                . "$link_text</time>\n";
        }
        else {
            $body_html = qq(<div class="tl-topbar"></div>\n);
        }

        $body_html .= join( '', map { $_->{ html } } @{ $page->{ articles } } );

        create_page(
            "$page->{ name }.html",
            $page->{ title }, $body_html, $archive_html, $config,
            $page->{ label }, $min_year, $max_year
        );
    }

    return;
}

sub create_week_page {

    my ( $year_week, $body_html, $archive, $config, $min_year, $max_year ) = @_;

    my $archive_html = html_for_archive(
        $archive, $year_week, '../..', $config->{ 'label-format' }
    );

    my ( $year, $week ) = split_year_week( $year_week );
    my $title = year_week_title( $config->{ 'label-format' }, $year, $week );
    path( "$config->{ 'output-dir' }/archive/$year/week" )->mkpath();
    create_page(
        "archive/$year/week/$week.html",
        $title, $body_html, $archive_html, $config,
        $title, $min_year, $max_year
    );
    return;
}

sub create_month_pages {

    my ( $days, $archive, $config, $min_year, $max_year ) = @_;

    my %years;
    for my $day ( @$days ) {
        my ( $year, $month, undef ) = split_date( $day->{ date } );
        unshift @{ $years{ $year }{ $month } }, $day;
    }

    my @month_names = get_month_names();
    my $archive_html = html_for_archive(
        $archive, undef, '../..', $config->{ 'label-format' }
    );

    for my $year ( sort keys %years ) {

        for my $month ( sort keys %{ $years{ $year } } ) {

            my $days_for_month = $years{ $year }{ $month };
            my $first_tp = parse_date( $days_for_month->[ 0 ]{ date } );
            my $month_name = decode_utf8( $first_tp->strftime( '%B' ) );
            my $nav_bar = html_for_month_nav_bar(
                $years{ $year }, $month, \@month_names
            );
            my $body_html = qq(<div class="tl-topbar"></div>\n)
                . qq(<div class="tl-month-overview">\n)
                . qq(  <h2 class="tl-month-year">$month_name )
                . qq(<a href="../../$year/">$year</a></h2>)
                . qq(  <dl class="tl-days">\n)
                . join( '',
                        map { html_for_day( $_ ) } @$days_for_month
                  )
                . "  </dl>\n"
                . $nav_bar
                . "</div>\n";

            create_page(
                "archive/$year/$month/index.html",
                "$month_name, $year", $body_html, $archive_html, $config,
                decode_utf8( $first_tp->strftime( '%b, %Y' ) ),
                $min_year, $max_year
            );
        }
    }
    return;
}

sub create_year_pages {

    my ( $days, $archive, $config, $min_year, $max_year ) = @_;

    my $start_year = ( split_date( $days->[ -1 ]{ date } ) )[ 0 ];
    my $end_year   = ( split_date( $days->[  0 ]{ date } ) )[ 0 ];

    my $archive_html = html_for_archive(
        $archive, undef, '..', $config->{ 'label-format' }
    );

    my $day_names_row = html_for_day_names_row();
    my $tp = parse_date( "$start_year-01-01" );
    my $date_index = $#$days;
    my $date = $days->[ $date_index ]{ date };
    my $year_index = 0;
    for my $year ( $start_year .. $end_year ) {

        my $body_html = qq(<div class="tl-topbar"></div>\n)
            . qq(<div class="tl-calendar">\n)
            . html_for_year_nav_bar(
                [ $start_year .. $end_year ], $year_index );
        $year_index++;

        while ( 1 ) {
            my $tbody;
            my $wday;
            my $week_active = 0;
            my $month_active = 0;
            my $current_mon = $tp->mon();
            my $month_name = decode_utf8( $tp->strftime( '%B' ) );
            my @row = ( '' ) x 7;
            while ( 1 ) {
                $wday = ( $tp->_wday + 6 ) % 7;
                if ( $date eq $tp->strftime( '%Y-%m-%d' ) ) {
                    $month_active = 1;
                    $week_active = 1;
                    $row[ $wday ] = html_link_for_day_number(
                        $days->[ $date_index ]
                    );
                    if ( $date_index > 0 ) {
                        $date_index--;
                        $date = $days->[ $date_index ]{ date };
                    }
                }
                else {
                    $row[ $wday ] = $tp->mday;
                }

                if ( $wday == 6 ) {
                    $tbody .= html_for_row( $year, $tp, \@row, $week_active );
                    $week_active = 0;
                    @row = ( '' ) x 7;
                }

                $tp += ONE_DAY;
                last if $tp->mon != $current_mon;
            }

            $tbody .= html_for_row( $year, $tp, \@row, $week_active )
                if $wday < 6;

            my $caption;
            if ( $month_active ) {
                my $uri = sprintf '%02d/', $current_mon;
                $caption = qq(<a href="$uri">$month_name</a>);
            }
            else {
                $caption = $month_name;
            }

            $body_html .= qq(  <table class="tl-month">\n)
                . "    <caption>$caption</caption>\n"
                . "    <thead>\n"
                . $day_names_row
                . "    </thead>\n"
                . "    <tbody>\n"
                . $tbody
                . "    </tbody>\n"
                . "  </table>\n";

            last if $tp->year != $year;
        }

        $body_html .= "</div>\n";

        path( "$config->{ 'output-dir' }/archive/$year")->mkpath();
        create_page(
            "archive/$year/index.html",
            $year, $body_html, $archive_html, $config,
            $year, $min_year, $max_year
        );
    }
    return;
}

sub create_page {

    my ( $path, $title, $body_html, $archive_html, $config,
         $label, $min_year, $max_year ) = @_;

    my $year_range = $min_year eq $max_year ?
        $min_year : "$min_year\x{2013}$max_year";

    my $slashes = $path =~ tr{/}{};
    my $css = join( '', '../' x $slashes, $config->{ css } );
    ( my $uri_path = $path ) =~ s/\bindex\.html$//;
    my $page_url = URI->new_abs( $uri_path, $config->{ 'blog-url' } );

    my $html = $config->{ template };

    for ( $html ) {
        s/ $RE_TITLE         / escape( $title ) /gxe;
        s/ $RE_YEAR_RANGE    / escape( $year_range ) /gxe;
        s/ $RE_LABEL         / escape( $label ) /gxe;
        s/ $RE_CSS           / escape( $css )/gxe;
        s/ $RE_NAME          / escape( $config->{ name } ) /gxe;
        s/ $RE_AUTHOR        / escape( $config->{ author } ) /gxe;
        s/ $RE_DESCRIPTION   / escape( $config->{ description } ) /gxe;
        s/ $RE_VERSION       / escape( $VERSION ) /gxe;
        s/ $RE_PAGE_URL      / escape( $page_url ) /gxe;
        s/ $RE_RSS_FEED_URL  / escape( $config->{ 'rss-feed-url' } ) /gxe;
        s/ $RE_JSON_FEED_URL / escape( $config->{ 'json-feed-url' } ) /gxe;
        s/ $RE_ARCHIVE       /$archive_html/gx;
        s/ $RE_BODY          /$body_html/x;
    }

    path( "$config->{ 'output-dir' }/$path" )
        ->append_utf8( { truncate => 1 }, $html );
    $config->{ quiet } or print "Created '$path'\n";

    return;
}

sub html_for_day {

    my $day = shift;

    my $day_number = ( split_date( $day->{ date } ) )[ 2 ];
    my $uri = "$day_number.html";
    my $title = escape( $day->{ title } );
    return qq(    <dt>$day_number</dt><dd><a href="$uri">$title</a></dd>\n);
}

sub html_for_month_nav_bar {

    my ( $active_months, $current_month, $names ) = @_;

    my $html = qq(  <nav>\n    <ul class="tl-month-navigation">\n);
    for my $mon ( 1..12 ) {
        my $month = sprintf '%02d', $mon;
        my $name = $names->[ $mon - 1 ];
        if ( exists $active_months->{ $month } ) {
            if ( $month eq $current_month ) {
                $html .= qq(      <li class="tl-self">$name</li>\n);
            }
            else {
                $html .= qq(      <li><a href="../$month/">$name</a></li>\n);
            }
        }
        else {
            $html .= qq(      <li>$name</li>\n);
        }
    }
    $html .= "    </ul>\n  </nav>\n";
    return $html;
}

sub html_for_day_names_row {

    my $tp = parse_date( '2019-01-07' ); # Monday

    my $names;
    for ( 0..6 ) {
        my $day_name = decode_utf8( $tp->strftime( '%a' ) );
        $names .= qq(        <th scope="col">$day_name</th>\n);
        $tp += ONE_DAY;
    }
    return "      <tr>\n        <td></td>\n$names      </tr>\n";
}

sub html_for_row {

    my ( $current_year, $tp, $row, $week_active ) = @_;

    my $week_html;
    my ( $year, $week ) = get_year_and_week( $tp );
    if ( $week_active ) {
        my $week_uri = $year == $current_year ? sprintf 'week/%02d.html', $week
            : sprintf '../%04d/week/%02d.html', $year, $week;
        $week_html = qq(<a href="$week_uri">$week</a>);
    }
    else {
        $week_html = $week;
    }

    return "      <tr>\n"
        . qq(        <th scope="row">$week_html</th>\n)
        . join( '', map { "        <td>$_</td>\n" } @$row )
        . "      </tr>\n";
}

sub html_link_for_day_number {

    my $day = shift;

    my ( $year, $month, $day_number ) = split_date( $day->{ date } );
    my $uri = "../$year/$month/$day_number.html";
    my $title = escape( $day->{ title } );
    my $mday = int( $day_number );
    return qq(<a href="$uri" title="$title">$mday</a>)
}

sub html_for_year_nav_bar {

    my ( $years, $year_index, $path ) = @_;

    $path //= '';

    my $nav;
    if ( $year_index > 0 ) {
        my $prev = $years->[ $year_index - 1 ];
        $nav = qq(    <div>\x{2190} <a href="../$prev/$path">$prev</a></div>\n)
    }
    else {
        $nav .= "    <div></div>\n";
    }

    $nav .= "    <h2>$years->[ $year_index ]</h2>\n";

    if ( $year_index < $#$years ) {
        my $next = $years->[ $year_index + 1 ];
        $nav .= qq(    <div><a href="../$next/$path">$next</a> \x{2192}</div>\n)
    }
    else {
        $nav .= "    <div></div>\n";
    }

    return qq(  <div class="tl-year">\n$nav  </div>\n);
}

sub html_for_date {

    my ( $date, $date_format, $title, $path ) = @_;

    my ( $year, $month, $day ) = split_date( $date );
    my $uri = "$path/$year/$month/$day.html";

    my $link_text = escape(
        decode_utf8(
            parse_date( $date )->strftime( $date_format )
        )
    );
    my $title_text = escape( $title );

    return qq(<time class="tl-date" datetime="$date">)
        . qq(<a href="$uri" title="$title_text">$link_text</a>)
        . "</time>\n";
}

sub html_for_archive {

    my ( $archive, $current_year_week, $path, $label_format ) = @_;

    my $html = qq(<dl>\n);
    for my $year ( sort { $b <=> $a } keys %$archive ) {
        $html .= qq(  <dt><a href="$path/$year/">$year</a></dt>\n)
            . "  <dd>\n    <ul>\n";
        for my $week ( @{ $archive->{ $year } } ) {
            my $year_week = join_year_week( $year, $week );
            if ( defined $current_year_week
                     && $year_week eq $current_year_week ) {
                $html .= qq(      <li class="tl-self">$week</li>\n);
            }
            else {
                my $title = escape(
                    year_week_title( $label_format, $year, $week )
                );
                my $uri = "$path/$year/week/$week.html";
                $html .= '      <li>'
                    . qq(<a href="$uri" title="$title">)
                    . $week . "</a></li>\n";
            }
        }
        $html .= "    </ul>\n  </dd>\n";
    }
    $html .= "</dl>\n";

    return $html;
}

sub html_link_for_day {

    my ( $day, $config ) = @_;

    my $title = escape( $day->{ title } );
    my $label = escape(
        decode_utf8(
            parse_date( $day->{ date } )->strftime( $config->{ 'date-format' } )
        )
    );

    my ( $year, $month, $day_number ) = split_date( $day->{ date } );
    my $uri = "../../$year/$month/$day_number.html";

    return qq(<a href="$uri" title="$label">$title</a>);
}

sub html_for_next_prev {

    my ( $days, $index, $config ) = @_;

    return '' if @$days == 1;

    my $html = qq(<nav class="tl-next-prev">\n);

    if ( $index ) {
        $html .= '  <div class="next">'
            . html_link_for_day( $days->[ $index - 1 ], $config )
            . '</div>'
            . qq(<div class="tl-right-arrow">\x{2192}</div>\n);
    }

    if ( $index < $#$days ) {
        $html .= qq(  <div class="tl-left-arrow">\x{2190}</div>)
            . '<div class="prev">'
            . html_link_for_day( $days->[ $index + 1 ], $config )
            . "</div>\n";
    }

    $html .= "</nav>\n";

    return $html;
}

sub create_archive {

    my $days = shift;

    my %seen;
    my %archive;
    for my $day ( @$days ) {
        my ( $year, $week ) = get_year_and_week( parse_date( $day->{ date } ) );
        my $year_week = join_year_week( $year, $week );
        if ( !exists $seen{ $year_week } ) {
            unshift @{ $archive{ sprintf '%04d', $year } },
                sprintf '%02d', $week;
            $seen{ $year_week } = 1;
        }
    }

    return \%archive
}

sub get_url_title_description {

    my ( $day, $config ) = @_;

    my $description = join( '', map { $_->{ html } } @{ $day->{ articles } } );
    my ( $year, $month, $day_number ) = split_date( $day->{ date } );
    my $url = URI->new_abs(
        "archive/$year/$month/$day_number.html",
        $config->{ 'blog-url' }
    )->as_string();

    return ( $url, $day->{ title }, $description );
}

sub get_month_names {

    my @names;
    for my $mon ( 1..12 ) {
        my $date = sprintf '2019-%02d-01', $mon;
        push @names, decode_utf8( parse_date( $date )->strftime( '%B' ) );
    }
    return @names;
}

sub get_end_of_day {

    return Time::Piece->localtime(
        Time::Piece->strptime( shift . ' 23:59:59', '%Y-%m-%d %H:%M:%S' )
    );
}

sub get_tag_path {

    ( my $name = shift ) =~ s/ /-/g;
    return "$name.html";
}

sub get_cloud_size {
    my ( $count, $min_count, $max_count ) = @_;

    return 1 if $min_count == $max_count;

    return 1 + int(
        4 * ( log( $count ) - log( $min_count ) )
        / ( log( $max_count ) - log( $min_count ) )
    );
}

sub create_tag_pages {

    my ( $days, $archive, $config, $min_year, $max_year ) = @_;

    my $tags = {};
    for my $day ( @$days ) {
        my $year = ( split_date( $day->{ date } ) )[ 0 ];
        for my $article ( reverse @{ $day->{ articles } } ) {
            for my $tag ( @{ $article->{ tags } } ) {
                $tags->{ $tag }{ count }++;
                unshift @{ $tags->{ $tag }{ years }{ $year } }, {
                    title => $article->{ title },
                    date  => $day->{ date },
                };
            }
        }
    }

    my $archive_html = html_for_archive(
        $archive, undef, '../../archive', $config->{ 'label-format' }
    );

    my %tag_info;
    for my $tag ( sort keys %$tags ) {
        my @years = sort keys %{ $tags->{ $tag }{ years } };
        $tag_info{ $tag }{ end_year } = $years[ -1 ];
        my $tag_path = get_tag_path( $tag );
        my $year_index = 0;
        for my $year ( @years ) {
            my $body_html = qq(<div class="tl-topbar"></div>\n)
                . qq(<div class="tl-tag-overview">\n)
                . html_for_year_nav_bar( \@years, $year_index, $tag_path )
                . "  <h2>$tag</h2>\n";
            $year_index++;

            my $current_month = '';
            my $rows = $tags->{ $tag }{ years }{ $year };
            for my $row ( @$rows ) {
                my $tp = parse_date( $row->{ date } );
                my $month_name = decode_utf8( $tp->strftime( '%B' ) );
                if ( $month_name ne $current_month ) {
                    $body_html .= "  </dl>\n" if $current_month ne '';
                    $body_html .= "  <h3>$month_name</h3>\n"
                        . qq(  <dl class="tl-days">\n);
                    $current_month = $month_name;
                }

                my $nr = ( split_date( $row->{ date } ) )[ 2 ];
                $body_html .= "    <dt>$nr</dt><dd>$row->{ title }</dd>\n";
                $tag_info{ $tag }{ count }++;
            }
            $body_html .= "  </dl>\n</div>\n";

            path( "$config->{ 'output-dir' }/tags/$year/")->mkpath();
            create_page(
                "tags/$year/$tag_path",
                $tag, $body_html, $archive_html, $config,
                $tag, $min_year, $max_year
            );
        }
    }

    # Create a page with a tag cloud
    my ( $min_count, $max_count );
    for my $tag ( keys %tag_info ) {
        $min_count = $tag_info{ $tag }{ count }
            if !defined $min_count || $tag_info{ $tag }{ count } < $min_count;
        $max_count = $tag_info{ $tag }{ count }
            if !defined $max_count || $tag_info{ $tag }{ count } > $max_count;
    }

    my $body_html = qq(<div class="tl-topbar"></div>\n)
        . qq(<div class="tl-tags-overview">\n)
        . "  <h2>$config->{ 'tags-title' }</h2>\n"
        . qq(  <ul class="tl-tag-cloud">\n);
    for my $tag ( sort keys %tag_info ) {
        my $tag_path = get_tag_path( $tag );
        my $size = get_cloud_size(
            $tag_info{ $tag }{ count }, $min_count, $max_count
        );
        $body_html .= qq(    <li class="tl-size-$size">)
            . qq(<a href="$tag_info{ $tag }{ end_year }/$tag_path">)
            . "$tag\x{202f}($tag_info{ $tag }{ count })</a></li>\n";
    }
    $body_html .= "  </ul>\n</div>\n";

    create_page(
        "tags/index.html",
        $config->{ 'tags-title' }, $body_html, $archive_html, $config,
        $config->{ 'tags-label' }, $min_year, $max_year
    );
    return;
}

sub create_rss_feed {

    my ( $days, $config ) = @_;

    my @items;
    my $todo = $config->{ 'feed-size' };

    for my $day ( @$days ) {

        my ( $url, $title, $description )
            = get_url_title_description( $day, $config );

        my $end_of_day = get_end_of_day( $day->{ date } );
        # RFC #822 in USA locale
        my $pub_date = $DAY_LIST[ $end_of_day->_wday() ]
            . sprintf( ', %02d ', $end_of_day->mday() )
            . $MON_LIST[ $end_of_day->_mon ]
            . $end_of_day->strftime( ' %Y %H:%M:%S %z' );

        push @items, join( '',
            '<item>',
            '<title>', escape( $title ), '</title>',
            '<link>', escape( $url ), '</link>',
            '<guid isPermaLink="true">', escape( $url ), '</guid>',
            '<pubDate>', escape( $pub_date ), '</pubDate>',
            '<description>', escape( $description ), '</description>',
            '</item>'
        );
        --$todo or last;
    }

    my $xml = join( '',
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '<channel>',
        '<title>', escape( $config->{ name } ), '</title>',
        '<link>', escape( $config->{ 'blog-url' } ), '</link>',
        '<description>', escape( $config->{ description } ),'</description>',
        '<atom:link href="', escape( $config->{ 'rss-feed-url' } ),
        '" rel="self" type="application/rss+xml" />',
        @items,
        '</channel>',
        '</rss>',
        "\n"
    );

    my $path = $config->{ 'rss-path' };
    path( "$config->{ 'output-dir' }/$path" )
        ->append_utf8( { truncate => 1 }, $xml );
    $config->{ quiet } or print "Created '$path'\n";

    return;
}

sub create_json_feed {

    my ( $days, $config ) = @_;

    my @items;
    my $todo = $config->{ 'feed-size' };

    for my $day ( @$days ) {

        my ( $url, $title, $description )
            = get_url_title_description( $day, $config );

        my $end_of_day = get_end_of_day( $day->{ date } );
        ( my $date_published = $end_of_day->strftime( '%Y-%m-%dT%H:%M:%S%z' ) )
            =~ s/(\d\d)$/:$1/a;

        push @items, {
            id    => $url,
            url   => $url,
            title => $title,
            content_html   => $description,
            date_published => $date_published,
        };

        --$todo or last;
    }

    my $feed = {
        version       => 'https://jsonfeed.org/version/1',
        title         => $config->{ name },
        home_page_url => $config->{ 'blog-url' },
        feed_url      => $config->{ 'json-feed-url' },
        description   => $config->{ description },
        author        => {
            name => $config->{ author },
        },
        items => \@items,
    };
    my $path = $config->{ 'json-path' };
    my $json = JSON::XS->new->utf8->indent->space_after->canonical
        ->encode( $feed );
    path( "$config->{ 'output-dir' }/$path" )
        ->append_raw( { truncate => 1 }, $json );
    $config->{ quiet } or print "Created '$path'\n";

    return;
}

sub year_week_title {

    my ( $format, $year, $week ) = @_;

    ( my $str = $format ) =~ s/%V/ sprintf '%02d', $week /ge;
    $str =~ s/%Y/ sprintf '%04d', $year /ge;
    return $str;
}

sub get_year_and_week {

    my $tp = shift;
    return ( $tp->strftime( '%G' ), $tp->week() );
}

sub get_year_week {

    my $date = shift;
    return join_year_week( get_year_and_week( parse_date( $date ) ) );
}

sub join_year_week {

    my ( $year, $week ) = @_;
    return sprintf '%04d-%02d', $year, $week;
}

sub split_year_week {

    return split /-/, shift;
}

sub split_date {

    return split /-/, shift;
}

sub parse_date {

    return Time::Piece->strptime( shift, '%Y-%m-%d' );
}

sub decode_utf8 {
    # UTF8 encoding for the Time::Piece strftime method, see bug #97539
    # https://rt.cpan.org/Public/Bug/Display.html?id=97539
    return decode( 'UTF-8', shift, Encode::FB_CROAK )
}

sub escape {

    my $str = shift;

    for ( $str ) {
        s/&/&amp;/g;
        s/</&lt;/g;
        s/>/&gt;/g;
        s/"/&quot;/g;
        s/'/&#x27;/g;
    }
    return $str;
}

sub rewrite_ast {

    # Rewrite an image at the start of a paragraph followed by some text
    # to an image with a figcaption inside a figure element

    my $ast = shift;

    my @nodes;
    my $it = $ast->iterator;
    while ( my ( $ev_type, $node ) = $it->next() ) {
        if ( $node->get_type() == NODE_PARAGRAPH && $ev_type == EVENT_EXIT ) {
            my $child = $node->first_child();
            next unless defined $child && $child->get_type() == NODE_IMAGE;
            next if $node->last_child() == $child;

            my $sibling = $child->next();
            if ( $sibling->get_type() == NODE_SOFTBREAK ) {
                # remove this sibling
                $sibling->unlink();
            }

            my $figcaption = CommonMark->create_custom_block(
                on_enter => '<figcaption>',
                on_exit  => '</figcaption>',
            );

            $sibling = $child->next();
            while ( $sibling ) {
                my $next = $sibling->next();
                $figcaption->append_child($sibling);
                $sibling = $next;
            }
            my $figure = CommonMark->create_custom_block(
                on_enter => '<figure>',
                on_exit  => '</figure>',
                children => [$child, $figcaption], # append_child unlinks for us
            );

            $node->replace( $figure );
            push @nodes, $node;
        }
    }

    return \@nodes;
}

sub convert_articles_to_html {

    my $items = shift;
    for my $item ( @$items ) {
        my @articles;
        for my $article ( @{ $item->{ articles } } ) {
            my $ast = CommonMark->parse_document( $article );
            my $nodes = rewrite_ast( $ast );
            my $html = qq(<article>\n)
                . $ast->render_html( OPT_UNSAFE )  # support (inline) HTML
                . "</article>\n";
            push @articles, { html => $html };
        }
        $item->{ articles } = \@articles;
    }
    return;
}

sub extract_identifier_and_heading {

    my $ast = shift;
    my $it = $ast->iterator;

    my ( $ev_type, $node ) = $it->next();
    ( $ev_type == EVENT_ENTER && $node->get_type() == NODE_DOCUMENT)
        or die 'Unexpected state encountered'; # should never happen

    ( $ev_type, $node ) = $it->next();
    ( $ev_type == EVENT_ENTER && $node->get_type() == NODE_HEADING)
        or die 'An article must start with a level 2 heading (none found)';

    my $level = $node->get_header_level();
    $level == 2
        or die "An article must start with a level 2 heading, not $level";

    my $heading = $node->render_html( OPT_UNSAFE );  # support (inline) HTML
    my $heading_node = $node;

    my $text = '';
    while ( my ( $ev_type, $node ) = $it->next() ) {
        last if $node->get_type() == NODE_HEADING && $ev_type == EVENT_EXIT;
        $text .= $node->get_literal() // '';
    }
    length( $text ) or die 'An article must have text after a heading';
    ( my $identifier = lc $text ) =~ s/\s+/-/g;

    $heading_node->unlink; # Output the title after modification later on

    return ( $identifier, $heading );
}

sub wrap_in_permalink {

    my ( $string, $config, $date, $identifier ) = @_;

    my ( $year, $month, $day_number ) = split_date( $date );
    my $uri = URI->new_abs(
        "archive/$year/$month/$day_number.html",
        $config->{ 'blog-url' }
    );
    $uri->fragment( $identifier );
    return qq(<a href="$uri">$string</a>);
}

sub insert_identifier_and_add_permalink {

    my ( $heading, $date, $identifier, $config ) = @_;

    return substr( $heading, 0, 3 )
        . ' id="' . escape( $identifier ) . '">'
        . wrap_in_permalink(
            substr( $heading, 4, -6 ), $config, $date, $identifier
        )
        . substr( $heading, -6 );
}

sub validate_identifier {
    my $identifier = shift;

    ref $identifier eq '' or die 'identifier is not a string';
    length $identifier or die 'identifier can not be empty';
    die 'identifier can not contain whitespace' if $identifier =~ /\s/;
    return;
}

sub validate_tags {

    my $tags = shift;

    ref $tags eq 'ARRAY' or die 'Tags must be specified as a list';

    my %seen;
    for my $tag ( @$tags ) {
        length $tag or die 'A tag must have a length';
        $tag =~ $RE_TAG or die "Invalid tag '$tag' found";
        ++$seen{ $tag } == 1 or die "Duplicate tag '$tag' found";
    }
    return;
}

sub html_for_tag {
    my ( $tag, $year, $config ) = @_;

    my $tag_path = get_tag_path( $tag );
    my $uri = URI->new_abs(
        "tags/$year/$tag_path",
        $config->{ 'blog-url' }
    );
    return qq(<a href="$uri">$tag</a>);
}

sub html_for_tags {

    my ( $tags, $date, $config ) = @_;

    my $year = ( split_date( $date ) )[ 0 ];
    return  join( '',
                  '<ul class="tl-tags">',
                  map(
                      '<li>' . html_for_tag( $_, $year, $config ) . '</li>',
                      @$tags
                  ),
                  "</ul>\n"
              );
}

sub convert_articles_with_metablock_to_html {

    my ( $items, $config ) = @_;

    my %ids;
    for my $item ( @$items ) {
        my @articles;
        my $article_no = 1;
        for my $article ( @{ $item->{ articles } } ) {
            try {
                my ( $yaml, $md ) = $article =~ $RE_YAML_MARKDOWN;
                $yaml or die 'No mandatory YAML block found';

                my $meta = Load $yaml;
                ref $meta eq 'HASH' or die 'YAML block must be a mapping';

                my $ast = CommonMark->parse_document( $md );
                my ( $identifier, $heading )
                    = extract_identifier_and_heading( $ast );
                if ( exists $meta->{ id } ) {
                    validate_identifier( $meta->{ id } );
                    $identifier = $meta->{ id };
                }

                # identifier must be globally unique
                die "Duplicate id '$identifier'"
                    ." (used later in $ids{ $identifier })"
                    if exists $ids{ $identifier };
                $ids{ $identifier } = $item->{ date };

                exists $meta->{tags} or die 'No tags are specified';
                validate_tags( $meta->{ tags } );

                my $nodes = rewrite_ast( $ast );
                my $html = qq(<article>\n)
                    . insert_identifier_and_add_permalink(
                        $heading, $item->{ date }, $identifier, $config
                    )
                    . $ast->render_html( OPT_UNSAFE )  # support (inline) HTML
                    . html_for_tags( $meta->{ tags }, $item->{ date }, $config )
                    . "</article>\n";

                push @articles, {
                    title => wrap_in_permalink(
                        substr($heading, 4, -6), $config, $item->{ date },
                        $identifier
                    ),
                    html => $html,
                    tags => $meta->{ tags },
                };
            }
            catch {
                my ( $error ) = $_ =~ /(.*) at /s;
                die "$error in article $article_no of $item->{ date }\n";
            };
            $article_no++;
        }
        $item->{ articles } = \@articles;
    }
    return;
}

sub strip {

    my $str = shift;
    $str =~ s/^\s+//;
    $str =~ s/\s+$//;
    return $str;
}

sub collect_days_and_pages {

    my $entries = shift;

    my @days;
    my @pages;
    my $state = 'unknown';
 ENTRY:
    for my $entry ( @$entries ) {
        if ($entry =~ $RE_DATE_TITLE ) {
            my $title = strip( $2 );
            $title ne '' or die "A day must have a title ($1)\n";
            push @days, {
                date     => $1,
                title    => $title,
                articles => [ $3 ],
            };
            $state = 'date-title';
            next ENTRY;
        }
        if ( $entry =~ $RE_AT_PAGE_TITLE ) {
            my $title = strip( $5 );
            $title ne '' or die "A page must have a title (\@$1)\n";
            push @pages, {
                name        => $1,
                label       => strip($2),
                date        => $3,
                'show-date' => $4 eq '!',
                title       => $title,
                articles    => [ $6 ],
            };
            $state = 'at-page-title';
            next ENTRY;
        }

        if ( $state eq 'date-title' ) {
            push @{ $days[ -1 ]{ articles } }, $entry;
            next ENTRY;
        }

        if ( $state eq 'at-page-title' ) {
            push @{ $pages[ -1]{ articles } }, $entry;
            next ENTRY;
        };

        die 'No date or page specified for first tumblelog entry';
    }

    @days  = sort { $b->{ date } cmp $a->{ date } } @days;
    @pages = sort { $b->{ date } cmp $a->{ date } } @pages;

    return ( \@days, \@pages );
}

sub read_entries {

    my $filename = shift;
    my $entries = [ grep { length $_ } split /^%\n/m,
                    path( $filename )->slurp_utf8() ];

    @$entries or die 'No entries found';

    return $entries;
}

sub show_usage_and_exit {

    my $exit_code = shift // 0;

    print { $exit_code ? *STDERR : *STDOUT } <<'END_USAGE';
NAME
        tumblelog.pl - Creates a static tumblelog

SYNOPSIS
        tumblelog.pl --template-filename TEMPLATE --output-dir HTDOCS
            --author AUTHOR --name BLOGNAME --description DESCRIPTION
            --blog-url URL
            [--days DAYS ] [--css CSS] [--date-format FORMAT] [--min-year YEAR]
            [--tags [--tags-label LABEL] [--tags-title TITLE]]
            [--feed-size SIZE] [--quiet] FILE
        tumblelog.pl --version
        tumblelog.pl --help
DESCRIPTION
        Processes the given FILE and creates static HTML pages using
        TEMPLATE and writes the generated files to directory HTDOCS.
        Uses the AUTHOR, BLOGNAME, DESCRIPTION and URL to create a
        JSON feed and an RSS feed.

        The --days argument specifies the number of days to show on the
        main page of the blog. It defaults to 14.

        The --css argument specifies the name of the stylesheet. It
        defaults to 'styles.css'.

        The --date-format argument specifies the date format to use
        for blog entries. It defaults to '%d %b %Y'.

        The --label-format argument specifies the format to use for the
        ISO 8601 week label. It defaults to 'week %V, %Y'

        The --min-year argument specificies the minimum year to use for the
        copyright message.

        The --tags option enables tags. Default off.

        The --tags-label argument specifies the label to use on the tags
        overview page. It defaults to 'tags'. Only used when tags are enabled.

        The --tags-title argument specifies the title to use on the tags
        overview page. It defaults to 'Tags'. Only used when tags are enabled.

        The --feed-size argument specifies the number of entries a feed
        has. It defaults to 25.

        The --quiet option prevents the program from printing information
        regarding the progress.

        The --version option shows the version number and exits.

        The --help option shows this information.
END_USAGE

    exit $exit_code;
}
