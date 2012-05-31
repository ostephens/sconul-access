#!/usr/bin/perl -w
use strict;
use LWP::UserAgent;
use HTML::Parser;
use CGI;
use CGI::Carp qw ( fatalsToBrowser );
use Data::Dumper;
use XML::Writer;


my $sconul_base_url = "http://www.access.sconul.ac.uk/";
my $sconul_az_url = "https://www.sconul.ac.uk/access/contacts_info/azresults.html";
my $sconul_member_url = "http://www.access.sconul.ac.uk/members/institution_html?ins_id=";
my $az_results;
my $member_results;
my $member_details;
my $inst_details;
my $institution_id;
my $institution_request;
my @institution_requests;
my $format;
my %az_results_set;
my %member_results_set;
my $institutions_href = {};
my $institution_name;
my $value_type;
my $writer = XML::Writer->new();

#Declare a LWP UserAgent we can use
my $ua = LWP::UserAgent->new;
$ua->agent("meanboyfriend.com/1.0");

my $query = new CGI;

$format = $query->param('format');
#Need to rewrite sanitation on institution parameter to allow value
#of 'all'. Possibly also to allow comma separated values? 
$institution_request = $query->param('institution');

&sanitise_parameters;


if (!$institution_request || $institution_request eq 'all') {
	#fetch SCONUL Access A-Z list
	$az_results = get_html($sconul_az_url); 
	#find relevant information from results page
	#Is this the best way to do this? We fetch the a-z page
	#put the values into an array and then use knowledge of
	#the order of the array to build the institutions_href
	#might be worth investigating other approaches?
	$inst_details = parse_az_results($az_results);
	&az_results_into_href;
	if (!$institution_request) {
		&open_results;
		&output_results;
		&close_results;
		exit;
		}
	}
else {
	@institution_requests = split(',', $institution_request);
	foreach my $code (@institution_requests) {
		$institutions_href->{ $code }->{'code'} = $code;
		}
	}
&get_member_details;

#Output successful results
&open_results;
&output_results;
&close_results; 

sub sanitise_parameters {
	return if (!$institution_request);
	return if ( $institution_request =~ m/^([0-9]{1,3},?)*$/i);
	return if ($institution_request eq 'all');
	&open_results;
	$writer->startTag("error");
	$writer->characters("Invalid Institution ID");
	$writer->endTag("error");
	&close_results;
	exit;
}

sub get_member_details {
	for my $inst_id ( keys (%$institutions_href) ) {
	$member_results = get_html($sconul_member_url.$inst_id);
	$institution_id = $inst_id;
	$member_details = parse_member_results($member_results);
	&member_results_into_href;
		}
}

sub parse_az_results {
	my $p = HTML::Parser->new(api_version => 3,
			start_h => [\&az_start_handler, "self,tagname,attr"],
			report_tags => [qw(a)],
			);
	$p->parse(shift || die) || die $!;
}

sub az_start_handler {

    my($self, $tag, $attr) = @_;
    return unless $tag eq "a";
    return unless exists $attr->{href};
    return unless $attr->{href} =~ m/.*\?ins_id\=[0-9]{1,3}.*/i;

    $attr->{href} =~ m/.*\?ins_id\=([0-9]{1,3})/i;
	$institution_id = $1;
	push @{ $az_results_set{$institution_id} }, $attr->{href};
    $self->handler(text  => [], '@{dtext}' );
    $self->handler(end   => \&az_end_handler, "self,tagname");
}

sub az_end_handler {

    my($self, $tag) = @_;
    my $text = join("", @{$self->handler("text")});
    $text =~ s/^\s+//;
    $text =~ s/\s+$//;
    $text =~ s/\s+/ /g;
	push @{ $az_results_set{$institution_id} }, $text;
    $self->handler("text", undef);
    $self->handler("start", \&az_start_handler);
    $self->handler("end", undef);
}

sub parse_member_results {

	my $p = HTML::Parser->new(api_version => 3,
		start_h => [\&member_start_handler, "self,tagname,attr"],
		report_tags => [qw(h2 th td)],
			);
	$p->parse(shift || die) || die $!;
}

sub member_start_handler {

    my($self, $tag, $attr) = @_;
    $self->handler(text  => [], '@{dtext}' );
    $self->handler(end   => \&member_end_handler, "self,tagname");
}

sub member_end_handler {
    my($self, $tag) = @_;
    my $text = join("", @{$self->handler("text")});
    return unless length($text)>1;
    $text =~ s/^\s+//;
    $text =~ s/\s+$//;
    $text =~ s/\s+/ /g;
	push @{ $member_results_set{$institution_id} }, $text;
    $self->handler("text", undef);
    $self->handler("start", \&member_start_handler);
    $self->handler("end", undef);
}

sub get_html {
	my $url = $_[0];
	my $response;

# Create a request
	my $req = HTTP::Request->new(GET => $url);
	my $res = $ua->request($req);

# Check if successful or not
	if ($res->is_success) {
		$response = $res->content;
		return $response;
        	}
	&open_results;
	$writer->startTag("error");
	$writer->characters("Sconul fetch get HTML failed: ".$url." : ".$res->status_line);
	$writer->endTag("error");
	&close_results;
	exit;
}

sub open_results {
	print "Content-type: text/xml\n\n";
	$writer->xmlDecl('UTF-8');
	$writer->startTag('sconul_access_results');
}

sub close_results {
	$writer->startTag('source');
	$writer->startTag('source_url');
	$writer->characters($sconul_base_url);
	$writer->endTag('source_url');
	$writer->startTag('rights');
	$writer->characters('Copyright SCONUL. SCONUL, 102 Euston Street, London, NW1 2HS. ');
	$writer->endTag('rights');
	$writer->endTag('source');
	$writer->endTag('sconul_access_results');
	$writer->end();
}


sub error {
}

sub output_results {
	for my $inst_id ( keys (%$institutions_href) ) {
	$writer->startTag('institution', 'code' => $inst_id, 'name' => $institutions_href->{$inst_id}->{name});
	if ($institutions_href->{$inst_id}->{sconul_url}) {
	$writer->startTag('inst_sconul_url');
	$writer->characters($institutions_href->{$inst_id}->{sconul_url});
	$writer->endTag('inst_sconul_url');
	}
	if ($institutions_href->{$inst_id}->{Web_site}) {
	$writer->startTag('website');
	$writer->characters($institutions_href->{$inst_id}->{Web_site});
	$writer->endTag('website');
	}
	if ($institutions_href->{$inst_id}->{Library_Web_site}) {
	$writer->startTag('library_website');
	$writer->characters($institutions_href->{$inst_id}->{Library_Web_site});
	$writer->endTag('library_website');
	}
	if ($institutions_href->{$inst_id}->{Library_Catalogue}) {
	$writer->startTag('library_catalogue');
	$writer->characters($institutions_href->{$inst_id}->{Library_Catalogue});
	$writer->endTag('library_catalogue');
	}
	if ($institutions_href->{$inst_id}->{Name}) {
	$writer->startTag('contact_name');
	$writer->characters($institutions_href->{$inst_id}->{Name});
	$writer->endTag('contact_name');
	}
	if ($institutions_href->{$inst_id}->{Post_Held}) {
	$writer->startTag('contact_title');
	$writer->characters($institutions_href->{$inst_id}->{Post_Held});
	$writer->endTag('contact_title');
	}
	if ($institutions_href->{$inst_id}->{Email_address}) {
	$writer->startTag('contact_email');
	$writer->characters($institutions_href->{$inst_id}->{Email_address});
	$writer->endTag('contact_email');
	}
	if ($institutions_href->{$inst_id}->{Telephone_number}) {
	$writer->startTag('contact_telephone');
	$writer->characters($institutions_href->{$inst_id}->{Telephone_number});
	$writer->endTag('contact_telephone');
	}
	if ($institutions_href->{$inst_id}->{Post_Code}) {
	$writer->startTag('contact_postcode');
	$writer->characters($institutions_href->{$inst_id}->{Post_Code});
	$writer->endTag('contact_postcode');
	}
	$writer->endTag('institution');
	}
}
sub az_results_into_href {
	for my $inst_id ( keys (%az_results_set) ) {
	$institutions_href->{ $inst_id } = {
			code=>$inst_id,
			name=>$az_results_set{$inst_id}->[1],
			sconul_url=>$sconul_base_url.$az_results_set{$inst_id}->[0]
					}
	}
}

sub member_results_into_href {
	for my $inst_id ( keys (%member_results_set) ) {
	$institutions_href->{ $inst_id }->{'code'} = $inst_id;
	$institutions_href->{ $inst_id }->{'name'} = 
				$member_results_set{$inst_id}->[0];
	$institutions_href->{ $inst_id }->{'sconul_url'} = $sconul_member_url.$inst_id;
           for (my $i = 1; $i < ($#{ $member_results_set{$inst_id} }); $i+=2 ) {
		$member_results_set{$inst_id}->[$i] =~ s/\s/_/g;
		$member_results_set{$inst_id}->[$i] =~ s/://g;
		if ($member_results_set{$inst_id}->[$i] eq 'Post_Held') {
			#the post held field sometime has an odd character on
			#the end, so this removes it
			$member_results_set{$inst_id}->[$i+1] =~ s/\W$//g;
			}
		if ($member_results_set{$inst_id}->[$i] eq 'Post_Code') {
			#the postcode field sometime has an odd character on
			#the end, so this removes it
			$member_results_set{$inst_id}->[$i+1] =~ s/\W$//g;
			}
		$institutions_href->{$inst_id}->
			{$member_results_set{$inst_id}->[$i]}=
				$member_results_set{$inst_id}->[$i+1];
			}
		}
}
