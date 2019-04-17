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

my $RE_TITLE      = qr/\[% \s* title      \s* %\]/x;
my $RE_YEAR_RANGE = qr/\[% \s* year-range \s* %\]/x;
my $RE_LABEL      = qr/\[% \s* label      \s* %\]/x;
my $RE_CSS        = qr/\[% \s* css        \s* %\]/x;
my $RE_NAME       = qr/\[% \s* name       \s* %\]/x;
my $RE_AUTHOR     = qr/\[% \s* author     \s* %\]/x;
my $RE_FEED_URL   = qr/\[% \s* feed-url   \s* %\]/x;
my $RE_BODY       = qr/\[% \s* body       \s* %\] \n/x;
my $RE_ARCHIVE    = qr/\[% \s* archive    \s* %\] \n/x;


create_blog( get_options() );

sub get_options {

    my %options = (
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
        'help'              => undef,
    );

    GetOptions(
        \%options,
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
        'help',
    );

    if ( $options{ help }) {
        show_help();
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
        if ( !defined $options{ $name } ) {
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

    $options{ filename } = $filename;
    $options{ template } = path( $options{ 'template-filename' } )
        ->slurp_utf8();
    $options{ 'feed-path' } = 'feed.json';
    $options{ 'feed-url' } = URI->new_abs(
        @options{ qw( feed-path blog-url ) }
    )->as_string();

    return \%options;
}

sub create_blog {

    my $options = shift;

    my $days = collect_days( read_tumblelog_entries( $options->{ filename } ) );

    my $max_year = ( split_date( $days->[  0 ]{ date } ) )[ 0 ];
    my $min_year = ( split_date( $days->[ -1 ]{ date } ) )[ 0 ];

    my $archive = create_archive( $days );

    create_index( $days, $archive, $options, $min_year, $max_year );

    create_day_and_week_pages(
        $days, $archive, $options, $min_year, $max_year
    );

    create_json_feed( $days, $options );

    return;
}

sub create_index {

    my ( $days, $archive, $options, $min_year, $max_year ) = @_;

    my $body_html;
    my $todo = $options->{ days };

    for my $day ( @$days ) {

        $body_html .= html_for_date(
            $day->{ date }, $options->{ 'date-format' }, 'archive'
        );

        $body_html .= html_for_entry( $_ ) for @{ $day->{ entries } };

        --$todo or last;
    }

    my $archive_html = html_for_archive( $archive, undef, 'archive' );

    my $label = 'home';
    my $title = join ' - ', $options->{ name }, $label;

    path( $options->{ 'output-dir' } )->mkpath();
    create_page(
        'index.html', $title, $body_html, $archive_html, $options,
        $label, $min_year, $max_year
    );

    return;
}

sub create_day_and_week_pages {

    my ( $days, $archive, $options, $min_year, $max_year ) = @_;

    my $year_week;
    my $week_body_html;
    my $current_year_week = get_year_week( $days->[ 0 ]{ date } );
    my $day_archive_html = html_for_archive( $archive, undef, '../..' );
    my $index = 0;
    for my $day ( @$days ) {

        my $day_body_html = html_for_date(
            $day->{ date }, $options->{ 'date-format' }, '../..'
        );

        $day_body_html .= html_for_entry( $_ ) for @{ $day->{ entries } };

        my ( $label, $title ) = label_and_title( $day, $options );
        my ( $year, $month, $day_number ) = split_date( $day->{ date } );
        my $next_prev_html = html_for_next_prev( $days, $index, $options );

        path( "$options->{ 'output-dir' }/archive/$year/$month")->mkpath();
        create_page(
            "archive/$year/$month/$day_number.html",
            $title, $day_body_html . $next_prev_html, $day_archive_html,
            $options,
            $label, $min_year, $max_year
        );

        $year_week = get_year_week( $day->{ date } );
        if ( $year_week eq $current_year_week ) {
            $week_body_html .= $day_body_html;
        }
        else {
            create_week_page(
                $current_year_week, $week_body_html, $archive, $options,
                $min_year, $max_year
            );
            $current_year_week = $year_week;
            $week_body_html = $day_body_html;
        }
        $index++;
    }

    create_week_page(
        $year_week, $week_body_html, $archive, $options,
        $min_year, $max_year
    );

    return;
}

sub create_week_page {

    my ( $year_week, $body_html, $archive, $options,
         $min_year, $max_year ) = @_;

    my $archive_html = html_for_archive( $archive, $year_week, '../..' );

    my ( $year, $week ) = split_year_week( $year_week );
    my $label = year_week_label( $options->{ 'label-format' }, $year, $week );
    my $title = join ' - ', $options->{ name }, $label;

    path( "$options->{ 'output-dir' }/archive/$year/week" )->mkpath();
    create_page(
        "archive/$year/week/$week.html",
        $title, $body_html, $archive_html, $options,
        $label, $min_year, $max_year
    );
    return;
}

sub create_page {

    my ( $path, $title, $body_html, $archive_html, $options,
         $label, $min_year, $max_year ) = @_;

    my $year_range = $min_year eq $max_year ?
        $min_year : "$min_year\x{2013}$max_year";

    my $slashes = $path =~ tr{/}{};
    my $css = join( '', '../' x $slashes, $options->{ css } );

    my $html = $options->{ template };

    for ( $html ) {
        s/ $RE_TITLE      / escape( $title )/gxe;
        s/ $RE_YEAR_RANGE / escape( $year_range )/gxe;
        s/ $RE_LABEL      / escape( $label ) /gxe;
        s/ $RE_CSS        / escape( $css )/gxe;
        s/ $RE_NAME       / escape( $options->{ name } ) /gxe;
        s/ $RE_AUTHOR     / escape( $options->{ author } ) /gxe;
        s/ $RE_FEED_URL   / escape( $options->{ 'feed-url' } )/gxe;
        s/ $RE_BODY       /$body_html/x;
        s/ $RE_ARCHIVE    /$archive_html/gx;
    }

    path( "$options->{ 'output-dir' }/$path" )
        ->append_utf8( { truncate => 1 }, $html );
    $options->{ quiet } or print "Created '$path'\n";

    return;
}

sub html_for_date {

    my ( $date, $date_format, $path ) = @_;

    my ( $year, $month, $day ) = split_date( $date );
    my $uri = "$path/$year/$month/$day.html";

    return qq(<time class="tl-date" datetime="$date"><a href="$uri">)
        . parse_date( $date )->strftime( $date_format )
        . "</a></time>\n";
}

sub html_for_entry {

    return qq(<article>\n)
        . CommonMark->markdown_to_html( shift  )
        . "</article>\n";
}

sub html_for_archive {

    my ( $archive, $current_year_week, $path ) = @_;

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
                my $uri = "$path/$year/week/$week.html";
                $html .= "        <li>"
                    . qq(<a href="$uri" title="$year_week">)
                    . $week . "</a></li>\n";
            }
        }
        $html .= "      </ul>\n    </dd>\n";
    }
    $html .= "  </dl>\n</nav>\n";

    return $html;
}

sub html_link_for_day {

    my ( $day, $options ) = @_;

    my $title = escape( $day->{ title } );
    my $label = escape(
        parse_date( $day->{ date } )->strftime( $options->{ 'date-format' } )
    );
    $title = $label if $title eq '';

    my ( $year, $month, $day_number ) = split_date( $day->{ date } );
    my $uri = "../../$year/$month/$day_number.html";

    return qq(<a href="$uri" title="$label">$title</a>);
}

sub html_for_next_prev {

    my ( $days, $index, $options ) = @_;

    return '' if @$days == 1;

    my $html = qq(<nav class="tl-next-prev">\n);

    if ( $index ) {
        $html .= '  <div class="next">'
            . html_link_for_day( $days->[ $index - 1 ], $options )
            . "</div>"
            . qq(<div class="tl-right-arrow">\x{2192}</div>\n);
    }

    if ( $index < $#$days ) {
        $html .= qq(  <div class="tl-left-arrow">\x{2190}</div>)
            . '<div class="prev">'
            . html_link_for_day( $days->[ $index + 1 ], $options )
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
        my $tp = parse_date( $day->{ date } );
        my $year = $tp->year();
        my $week = $tp->week();
        my $year_week = join_year_week( $year, $week );
        if ( !exists $seen{ $year_week } ) {
            unshift @{ $archive{ $year } }, $week;
            $seen{ $year_week } = 1;
        }
    }

    return \%archive
}

sub create_json_feed {

    my ( $days, $options ) = @_;

    my @items;
    my $todo = $options->{ days };

    for my $day ( @$days ) {
        my $html;
        $html .= html_for_entry( $_ )
            for @{ $day->{ entries } };

        my ( $year, $month, $day_number ) = split_date( $day->{ date } );
        my $url = URI->new_abs(
            "archive/$year/$month/$day_number.html",
            $options->{ 'blog-url' }
        )->as_string();
        my $title = $day->{ title };
        if ( $title eq '' ) {
            $title = parse_date( $day->{ date } )->strftime(
                $options->{ 'date-format' }
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
        title         => $options->{ 'name' },
        home_page_url => $options->{ 'blog-url' },
        feed_url      => $options->{ 'feed-url' },
        author        => {
            name => $options->{ author },
        },
        items => \@items,
    };
    my $path = $options->{ 'feed-path' };
    my $json = JSON::XS->new->utf8->indent->space_after->canonical
        ->encode( $feed );
    path( "$options->{ 'output-dir' }/$path" )
        ->append_raw( { truncate => 1 }, $json );
    $options->{ quiet } or print "Created '$path'\n";

    return;
}

sub label_and_title {

    my ( $day, $options ) = @_;

    my $label = parse_date( $day->{ date } )
        ->strftime( $options->{ 'date-format' } );
    my $title = $day->{ title };
    if ( $title ne '' ) {
        $title = join ' - ', $title, $options->{ name };
    }
    else {
        $title = join ' - ', $options->{ name }, $label;
    }
    return ( $label, $title );
}

sub year_week_label {

    my ( $format, $year, $week ) = @_;

    ( my $str = $format ) =~ s/%V/ sprintf '%02d', $week /ge;
    $str =~ s/%Y/ sprintf '%04d', $year /ge;
    return $str;
}

sub get_year_week {

    my $date = shift;
    my $tp = parse_date( $date );
    return join_year_week( $tp->year(), $tp->week() );
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
        defined $date or die "No date specified for first tumblelog entry";
        push @{ $days[ -1 ]{ entries } }, $entry;
    }

    @days = sort { $b->{ date } cmp $a->{ date } } @days;

    return \@days;
}

sub read_tumblelog_entries {

    my $filename = shift;
    my $entries = [ split /^%\n/m, path( $filename )->slurp_utf8() ];

    @$entries or die "No blog entries found";

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

        The --help option shows this information.
END_HELP

    return;
}
