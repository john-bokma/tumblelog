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
use HTML::Entities;
use Path::Tiny;
use CommonMark;
use Time::Piece;
use Getopt::Long;

my %options = (
    'template-filename' => undef,
    'output-dir'        => undef,
    'author'            => undef,
    'name'              => undef,
    'blog-url'          => undef,
    'days'              => 14,
    'css-url'           => 'styles.css',
    'date-format'       => '%d %b %Y',
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
    'css-url=s',
    'date-format=s',
    'quiet',
    'help',
);

if ( $options{ help }) {
    show_help();
    exit;
}

my %required = (
    'template-filename' =>
        "Use --template-filename to specify a template",
    'output-dir' =>
        "Use --output-dir to specify an output directory for HTML files",
    'author' =>
        "Use --author to specify an author name",
    'name' =>
        "Use --name to specify a name for the blog and its feed",
    'blog-url' =>
        "Use --blog-url to specify the URL of the blog itself",
);

for my $name ( sort keys %required ) {
    if ( !defined $options{ $name } ) {
        warn "$required{ $name }\n\n";
        show_help();
        exit( 1 );
    }
}

my $tumblelog_filename = shift @ARGV;
if ( !defined $tumblelog_filename ) {
    warn "Specify a filename that contains the log entries\n\n";
    show_help();
    exit( 1 );
}
warn "Additional arguments have been skipped\n" if @ARGV;

$options{ template    } = path( $options{ 'template-filename' } )->slurp_utf8();
$options{ 'feed-path' } = 'feed.json';
$options{ 'feed-url'  } = URI->new_abs( @options{ qw( feed-path blog-url ) } )
    ->as_string();

my $collected = collect_weekly_entries(
    collect_daily_entries(
        read_tumblelog_entries( $tumblelog_filename )
    )
);

my @year_weeks = sort { $b cmp $a } keys %$collected;
my ( $max_year, undef ) = split_year_week( $year_weeks[  0 ] );
my ( $min_year, undef ) = split_year_week( $year_weeks[ -1 ] );

my $archive = create_archive( \@year_weeks );

create_index(
    \@year_weeks, $collected, $archive, \%options, $min_year, $max_year
);

create_other_pages( $_, $collected, $archive, \%options, $min_year, $max_year )
    for @year_weeks;

create_json_feed( \@year_weeks, $collected, \%options );


sub create_index {

    my ( $period, $collected, $archive, $options, $min_year, $max_year ) = @_;

    my $body_html;
    my $todo = $options->{ days };
  YEAR_WEEK:
    for my $year_week ( @$period ) {
        my @dates = sort { $b cmp $a } keys %{ $collected->{ $year_week } };
        for my $date ( @dates ) {
            $body_html .= html_for_date(
                $date, $options->{ 'date-format' }, 'archive'
            );

            $body_html .= html_for_entry( $_ )
                for @{ $collected->{ $year_week }{ $date } };

            --$todo or last YEAR_WEEK;
        }
    }

    my $archive_html = html_for_archive( $archive, 'none', 'archive' );

    create_page(
        'index.html', $body_html, $archive_html, $options,
        'home', $min_year, $max_year
    );
    return;
}

sub create_other_pages {

    my ( $year_week, $collected, $archive, $options,
         $min_year, $max_year ) = @_;

    my $week_body_html;
    my @dates = sort { $b cmp $a } keys %{ $collected->{ $year_week } };
    for my $date ( @dates ) {
        my $day_body_html = html_for_date(
            $date, $options->{ 'date-format' }, '../..'
        );
        for my $entry ( @{ $collected->{ $year_week }{ $date } } ) {
            $day_body_html .= html_for_entry( $entry );
        }

        my $archive_html = html_for_archive( $archive, '', '../..' );

        my ( $year, $month, $day ) = split /-/, $date;
        path( "$options->{ 'output-dir' }/archive/$year/$month")->mkpath();
        create_page(
            "archive/$year/$month/$day.html",
            $day_body_html, $archive_html, $options,
            parse_date( $date )->strftime( $options->{ 'date-format' } ),
            $min_year, $max_year
        );

        $week_body_html .= $day_body_html;
    }

    my $archive_html = html_for_archive( $archive, $year_week, '../..' );

    my ( $year, $week ) = split_year_week( $year_week );
    path( "$options->{ 'output-dir' }/archive/$year/week" )->mkpath();
    create_page(
        "archive/$year/week/$week.html",
        $week_body_html, $archive_html, $options,
        "week $week, $year" , $min_year, $max_year
    );
    return;
}

sub create_page {

    my ( $path, $body_html, $archive_html, $options,
         $label, $min_year, $max_year ) = @_;

    my $year_range = $min_year eq $max_year ?
        $min_year : "$min_year - $max_year";

    my $slashes = $path =~ tr{/}{};
    my $css = $options->{ 'css-url' };
    $css = join( '', '../' x $slashes ) . $css;

    my $html = $options->{ template };

    for ( $html ) {
        s/\[% \s+ year-range \s+ %\]/$year_range/gx;
        s/\[% \s+ label    \s+ %\]/ encode_entities( $label ) /gxe;
        s/\[% \s+ css      \s+ %\]/$css/gx;
        s/\[% \s+ name     \s+ %\]/ encode_entities( $options->{ name } )/gxe;
        s/\[% \s+ author   \s+ %\]/ encode_entities( $options->{ author } )/gxe;
        s/\[% \s+ feed-url \s+ %\]/ $options->{ 'feed-url' }/gx;
        s/\[% \s+ body     \s+ %\]\n/$body_html/x;
        s/\[% \s+ archive  \s+ %\]\n/$archive_html/gx;

    }

    path( "$options->{ 'output-dir' }/$path" )->spew_utf8( $html );
    $options->{ quiet } or print "Created '$path'\n";
    return;
}

sub html_for_date {

    my ( $date, $date_format, $path ) = @_;

    my ( $year, $month, $day ) = split /-/, $date;
    my $uri = "$path/$year/$month/$day.html";

    return qq(<time class="tl-date" datetime="$date"><a href="$uri">)
        . parse_date( $date )->strftime( $date_format )
        . "</a></time>\n";
}

sub html_for_entry {

    my $entry = shift;
    return qq(<article>\n)
        . CommonMark->markdown_to_html( $entry  )
        . "</article>\n";
}

sub html_for_archive {

    my ( $archive, $current_year_week, $path ) = @_;

    my $html = qq(<nav>\n  <dl class="tl-archive">\n);
    for my $year ( sort { $b <=> $a } keys %$archive ) {
        $html .= "    <dt>$year</dt>\n    <dd>\n      <ul>\n";
        for my $week ( @{ $archive->{ $year } } ) {
            my $year_week = year_week( $year, $week );
            if ( $year_week eq $current_year_week ) {
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

sub create_archive {

    my $year_weeks = shift;

    my %archive;
    for my $year_week ( @$year_weeks ) {
        my ( $year, $week ) = split_year_week( $year_week );
        unshift @{ $archive{ $year } }, $week;
    }
    return \%archive
}

sub create_json_feed {

    my ( $period, $collected, $options ) = @_;

    my @items;
    my $todo = $options->{ days };
  YEAR_WEEK:
    for my $year_week ( @$period ) {
        my @dates = sort { $b cmp $a } keys %{ $collected->{ $year_week } };
        for my $date ( @dates ) {
            my $html;
            $html .= html_for_entry( $_ )
                for @{ $collected->{ $year_week }{ $date } };

            my ( $year, $month, $day ) = split /-/, $date;
            my $url = URI->new_abs(
                "archive/$year/$month/$day.html",
                $options->{ 'blog-url' }
            )->as_string();
            my $title = parse_date( $date )
                ->strftime( $options->{ 'date-format' } );
            push @items, {
                id    => $url,
                url   => $url,
                title => $title,
                content_html   => $html,
                date_published => $date,
            };

            --$todo or last YEAR_WEEK;
        }
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
    my $json = JSON::XS->new->utf8->pretty->canonical->encode( $feed );
    path( "$options->{ 'output-dir' }/$path" )->spew_raw( $json );
    $options->{ quiet } or print "Created '$path'\n";

    return;
}

sub year_week {

    my ( $year, $week ) = @_;
    return sprintf '%04d-%02d', $year, $week;
}

sub split_year_week {

    return split /-/, shift;
}

sub parse_date {

    return Time::Piece->strptime( shift, '%Y-%m-%d' );
}

sub collect_weekly_entries {

    my $entries = shift;

    my %collected;
    my @dates = sort { $b cmp $a } keys %$entries;
    for my $date ( @dates ) {
        my $tp = parse_date( $date );
        my $year_week = year_week( $tp->year(), $tp->week() );
        $collected{ $year_week }{ $date } = $entries->{ $date };
    }
    return \%collected;
}

sub collect_daily_entries {

    my $entries = shift;

    my $date;
    my %collected;
    for my $entry ( @$entries ) {
        if ( $entry =~ /^(\d{4}-\d{2}-\d{2})\n(.*)/s ) {
            $date = $1;
            $entry = $2;
        }
        defined $date or die "No date specified for first tumblelog entry";
        push @{ $collected{ $date } }, $entry;
    }

    return \%collected;
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
            [--days DAYS ] [--css-url URL] [--date-format FORMAT] [--quiet] FILE
        tumblelog.pl --help
DESCRIPTION
        Processes the given FILE and creates static HTML pages using
        TEMPLATE and writes the generated files to directory HTDOCS.
        Uses the AUTHOR, BLOGNAME, and URL to create a JSON feed.

        The --days argument specifies the number of days to show on the
        main page of the blog. It defaults to 14.

        The --css-url argument specifies the name of the stylesheet. It
        defaults to 'styles.css'.

        The --date-format argument specifies the date format to use
        for blog entries. It defaults to '%d %b %Y'.

        The --quiet option prevents the program from printing information
        regarding the progress.

        The --help option shows this information.
END_HELP

    return;
}
