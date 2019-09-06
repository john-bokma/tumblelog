#!/usr/bin/perl
#
# (c) John Bokma, 2019
#
# This program is free software; you can redistribute it and/or modify it
# under the same terms as Perl itself.

use strict;
use warnings;

use URI;
use JSON::XS;
use Path::Tiny;
use CommonMark;
use Time::Piece;
use Getopt::Long;

my $VERSION = '1.0.8';

my $RE_TITLE      = qr/\[% \s* title      \s* %\]/x;
my $RE_YEAR_RANGE = qr/\[% \s* year-range \s* %\]/x;
my $RE_LABEL      = qr/\[% \s* label      \s* %\]/x;
my $RE_CSS        = qr/\[% \s* css        \s* %\]/x;
my $RE_NAME       = qr/\[% \s* name       \s* %\]/x;
my $RE_AUTHOR     = qr/\[% \s* author     \s* %\]/x;
my $RE_VERSION    = qr/\[% \s* version    \s* %\]/x;
my $RE_PAGE_URL   = qr/\[% \s* page-url   \s* %\]/x;
my $RE_FEED_URL   = qr/\[% \s* feed-url   \s* %\]/x;
my $RE_BODY       = qr/\[% \s* body       \s* %\] \n/x;
my $RE_ARCHIVE    = qr/\[% \s* archive    \s* %\] \n/x;


create_blog( get_config() );

sub get_config {

    my %arguments = (
        'template-filename' => undef,
        'output-dir'        => undef,
        'author'            => undef,
        'name'              => undef,
        'blog-url'          => undef,
        'days'              => 14,
        'css'               => 'styles.css',
        'date-format'       => '%d %b %Y',
        'label-format'      => 'week %V, %Y',
        'quiet'             => undef,
        'version'           => undef,
        'help'              => undef,
    );

    GetOptions(
        \%arguments,
        'template-filename=s',
        'output-dir=s',
        'author=s',
        'name=s',
        'blog-url=s',
        'days=i',
        'css=s',
        'date-format=s',
        'label-format=s',
        'quiet',
        'version',
        'help',
    );

    if ( $arguments{ help } ) {
        show_help();
        exit;
    }

    if ( $arguments{ version } ) {
        print "$VERSION\n";
        exit;
    }

    my %required = (
        'template-filename' =>
            'Use --template-filename to specify a template',
        'output-dir' =>
            'Use --output-dir to specify an output directory for HTML files',
        'author' =>
            'Use --author to specify an author name',
        'name' =>
            'Use --name to specify a name for the blog and its feed',
        'blog-url' =>
            'Use --blog-url to specify the URL of the blog itself',
    );

    for my $name ( sort keys %required ) {
        if ( !defined $arguments{ $name } ) {
            warn "$required{ $name }\n\n";
            show_help();
            exit( 1 );
        }
    }

    my $filename = shift @ARGV;
    if ( !defined $filename ) {
        warn "Specify a filename that contains the blog entries\n\n";
        show_help();
        exit( 1 );
    }
    warn "Additional arguments have been skipped\n" if @ARGV;

    my %config = %arguments;
    $config{ filename } = $filename;
    $config{ template } = path( $config{ 'template-filename' } )
        ->slurp_utf8();
    $config{ 'feed-path' } = 'feed.json';
    $config{ 'feed-url' } = URI->new_abs(
        @config{ qw( feed-path blog-url ) }
    )->as_string();

    return \%config;
}

sub create_blog {

    my $config = shift;

    my $days = collect_days( read_tumblelog_entries( $config->{ filename } ) );

    my $max_year = ( split_date( $days->[  0 ]{ date } ) )[ 0 ];
    my $min_year = ( split_date( $days->[ -1 ]{ date } ) )[ 0 ];

    my $archive = create_archive( $days );

    create_index( $days, $archive, $config, $min_year, $max_year );

    create_day_and_week_pages(
        $days, $archive, $config, $min_year, $max_year
    );

    create_json_feed( $days, $config );

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
        );

        $body_html .= html_for_entry( $_ ) for @{ $day->{ entries } };

        --$todo or last;
    }

    my $archive_html = html_for_archive(
        $archive, undef, 'archive', $config->{ 'label-format' }
    );

    my $label = 'home';
    my $title = join ' - ', $config->{ name }, $label;

    path( $config->{ 'output-dir' } )->mkpath();
    create_page(
        'index.html', $title, $body_html, $archive_html, $config,
        $label, $min_year, $max_year
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
        );

        $day_body_html .= html_for_entry( $_ ) for @{ $day->{ entries } };

        my ( $label, $title ) = label_and_title( $day, $config );
        my ( $year, $month, $day_number ) = split_date( $day->{ date } );
        my $next_prev_html = html_for_next_prev( $days, $index, $config );

        path( "$config->{ 'output-dir' }/archive/$year/$month")->mkpath();
        create_page(
            "archive/$year/$month/$day_number.html",
            $title, $day_body_html . $next_prev_html, $day_archive_html,
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

sub create_week_page {

    my ( $year_week, $body_html, $archive, $config, $min_year, $max_year ) = @_;

    my $archive_html = html_for_archive(
        $archive, $year_week, '../..', $config->{ 'label-format' }
    );

    my ( $year, $week ) = split_year_week( $year_week );
    my $label = year_week_label( $config->{ 'label-format' }, $year, $week );
    my $title = join ' - ', $config->{ name }, $label;

    path( "$config->{ 'output-dir' }/archive/$year/week" )->mkpath();
    create_page(
        "archive/$year/week/$week.html",
        $title, $body_html, $archive_html, $config,
        $label, $min_year, $max_year
    );
    return;
}

sub create_page {

    my ( $path, $title, $body_html, $archive_html, $config,
         $label, $min_year, $max_year ) = @_;

    my $year_range = $min_year eq $max_year ?
        $min_year : "$min_year\x{2013}$max_year";

    my $slashes = $path =~ tr{/}{};
    my $css = join( '', '../' x $slashes, $config->{ css } );
    my $page_url = URI->new_abs(
        $path eq 'index.html' ? '/' : $path,
        $config->{ 'blog-url' }
    );

    my $html = $config->{ template };

    for ( $html ) {
        s/ $RE_TITLE      / escape( $title ) /gxe;
        s/ $RE_YEAR_RANGE / escape( $year_range ) /gxe;
        s/ $RE_LABEL      / escape( $label ) /gxe;
        s/ $RE_CSS        / escape( $css )/gxe;
        s/ $RE_NAME       / escape( $config->{ name } ) /gxe;
        s/ $RE_AUTHOR     / escape( $config->{ author } ) /gxe;
        s/ $RE_VERSION    / escape( $VERSION ) /gxe;
        s/ $RE_PAGE_URL   / escape( $page_url ) /gxe;
        s/ $RE_FEED_URL   / escape( $config->{ 'feed-url' } ) /gxe;
        s/ $RE_BODY       /$body_html/x;
        s/ $RE_ARCHIVE    /$archive_html/gx;
    }

    path( "$config->{ 'output-dir' }/$path" )
        ->append_utf8( { truncate => 1 }, $html );
    $config->{ quiet } or print "Created '$path'\n";

    return;
}

sub html_for_date {

    my ( $date, $date_format, $title, $path ) = @_;

    my ( $year, $month, $day ) = split_date( $date );
    my $uri = "$path/$year/$month/$day.html";

    my $link_text = escape( parse_date( $date )->strftime( $date_format ) );
    my $title_text = $title ne '' ? escape( $title ) : $link_text;

    return qq(<time class="tl-date" datetime="$date">)
        . qq(<a href="$uri" title="$title_text">$link_text</a>)
        . "</time>\n";
}

sub html_for_entry {

    return qq(<article>\n)
        . CommonMark->markdown_to_html( shift  )
        . "</article>\n";
}

sub html_for_archive {

    my ( $archive, $current_year_week, $path, $label_format ) = @_;

    my $html = qq(<nav>\n  <dl class="tl-archive">\n);
    for my $year ( sort { $b <=> $a } keys %$archive ) {
        $html .= "    <dt>$year</dt>\n    <dd>\n      <ul>\n";
        for my $week ( @{ $archive->{ $year } } ) {
            my $year_week = join_year_week( $year, $week );
            if ( defined $current_year_week
                     && $year_week eq $current_year_week ) {
                $html .= qq(        <li class="tl-self">$week</li>\n);
            }
            else {
                my $title = escape(
                    year_week_label( $label_format, $year, $week )
                );
                my $uri = "$path/$year/week/$week.html";
                $html .= '        <li>'
                    . qq(<a href="$uri" title="$title">)
                    . $week . "</a></li>\n";
            }
        }
        $html .= "      </ul>\n    </dd>\n";
    }
    $html .= "  </dl>\n</nav>\n";

    return $html;
}

sub html_link_for_day {

    my ( $day, $config ) = @_;

    my $title = escape( $day->{ title } );
    my $label = escape(
        parse_date( $day->{ date } )->strftime( $config->{ 'date-format' } )
    );
    $title = $label if $title eq '';

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

sub create_json_feed {

    my ( $days, $config ) = @_;

    my @items;
    my $todo = $config->{ days };

    for my $day ( @$days ) {
        my $html;
        $html .= html_for_entry( $_ )
            for @{ $day->{ entries } };

        my ( $year, $month, $day_number ) = split_date( $day->{ date } );
        my $url = URI->new_abs(
            "archive/$year/$month/$day_number.html",
            $config->{ 'blog-url' }
        )->as_string();
        my $title = $day->{ title };
        if ( $title eq '' ) {
            $title = parse_date( $day->{ date } )->strftime(
                $config->{ 'date-format' }
            );
        }
        push @items, {
            id    => $url,
            url   => $url,
            title => $title,
            content_html   => $html,
            date_published => $day->{ date },
        };

        --$todo or last;
    }

    my $feed = {
        version       => 'https://jsonfeed.org/version/1',
        title         => $config->{ 'name' },
        home_page_url => $config->{ 'blog-url' },
        feed_url      => $config->{ 'feed-url' },
        author        => {
            name => $config->{ author },
        },
        items => \@items,
    };
    my $path = $config->{ 'feed-path' };
    my $json = JSON::XS->new->utf8->indent->space_after->canonical
        ->encode( $feed );
    path( "$config->{ 'output-dir' }/$path" )
        ->append_raw( { truncate => 1 }, $json );
    $config->{ quiet } or print "Created '$path'\n";

    return;
}

sub label_and_title {

    my ( $day, $config ) = @_;

    my $label = parse_date( $day->{ date } )
        ->strftime( $config->{ 'date-format' } );
    my $title = $day->{ title };
    if ( $title ne '' ) {
        $title = join ' - ', $title, $config->{ name };
    }
    else {
        $title = join ' - ', $config->{ name }, $label;
    }
    return ( $label, $title );
}

sub year_week_label {

    my ( $format, $year, $week ) = @_;

    ( my $str = $format ) =~ s/%V/ sprintf '%02d', $week /ge;
    $str =~ s/%Y/ sprintf '%04d', $year /ge;
    return $str;
}

sub get_year_and_week {

    my $tp = shift;
    return ( $tp->strftime('%G'), $tp->week() );
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

sub strip {

    my $str = shift;
    $str =~ s/^\s+//;
    $str =~ s/\s+$//;
    return $str;
}

sub collect_days {

    my $entries = shift;

    my $date;
    my @days;
    for my $entry ( @$entries ) {
        if ( $entry =~ /^(\d{4}-\d{2}-\d{2})(.*?)\n(.*)/s ) {
            $date = $1;
            push @days, {
                date    => $date,
                title   => strip($2),
                entries => [],
            };
            $entry = $3;
        }
        defined $date or die 'No date specified for first tumblelog entry';
        push @{ $days[ -1 ]{ entries } }, $entry;
    }

    @days = sort { $b->{ date } cmp $a->{ date } } @days;

    return \@days;
}

sub read_tumblelog_entries {

    my $filename = shift;
    my $entries = [ split /^%\n/m, path( $filename )->slurp_utf8() ];

    @$entries or die 'No blog entries found';

    return $entries;
}

sub show_help {

    print <<'END_HELP';
NAME
        tumblelog.pl - Creates a static tumblelog

SYNOPSIS
        tumblelog.pl --template-filename TEMPLATE --output-dir HTDOCS
            --author AUTHOR -name BLOGNAME --blog-url URL
            [--days DAYS ] [--css CSS] [--date-format FORMAT] [--quiet] FILE
        tumblelog.pl --version
        tumblelog.pl --help
DESCRIPTION
        Processes the given FILE and creates static HTML pages using
        TEMPLATE and writes the generated files to directory HTDOCS.
        Uses the AUTHOR, BLOGNAME, and URL to create a JSON feed.

        The --days argument specifies the number of days to show on the
        main page of the blog. It defaults to 14.

        The --css argument specifies the name of the stylesheet. It
        defaults to 'styles.css'.

        The --date-format argument specifies the date format to use
        for blog entries. It defaults to '%d %b %Y'.

        The --label-format argument specifies the format to use for the
        ISO 8601 week label. It defaults to 'week %V, %Y'

        The --quiet option prevents the program from printing information
        regarding the progress.

        The --version option shows the version number and exits.

        The --help option shows this information.
END_HELP

    return;
}
