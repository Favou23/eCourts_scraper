# import json
# import datetime
# import click
# from .scraper import ECourtsScraper
# from .utils import save_json


# @click.group()
# def cli():
#     pass


# @cli.command()
# @click.option('--cnr', help='Case CNR number')
# @click.option('--type', 'case_type', help='Case type')
# @click.option('--number', type=int, help='Case number')
# @click.option('--year', type=int, help='Case year')
# @click.option('--download-pdf', is_flag=True, help='Download case PDF if available')
# @click.option('--today', is_flag=True, help='Assume listing date is today (alias)')
# @click.option('--tomorrow', is_flag=True, help='Assume listing date is tomorrow (alias)')
# @click.option('--when', type=click.Choice(['today','tomorrow']), default='today', help='Which date to check listings for')
# def check(cnr, case_type, number, year, download_pdf, today, tomorrow, when):
#     """Check whether a case is listed today or tomorrow."""
#     if today and tomorrow:
#         click.echo('--today and --tomorrow are mutually exclusive')
#         return
#     if today:
#         when = 'today'
#     if tomorrow:
#         when = 'tomorrow'

#     scraper = ECourtsScraper()
#     target_date = datetime.date.today() if when == 'today' else datetime.date.today() + datetime.timedelta(days=1)
#     if cnr:
#         res = scraper.search_case_in_cause_list(target_date, cnr)
#     else:
#         if not (case_type and number and year):
#             click.echo('Provide either --cnr or --type/--number/--year')
#             return
#         q = f"{case_type} {number} {year}"
#         res = scraper.search_case_in_cause_list(target_date, q)

#     click.echo(json.dumps(res, indent=2, ensure_ascii=False))
#     save_json(res, f'result_{target_date.isoformat()}.json')


# @cli.command()
# @click.option('--date', type=click.Choice(['today', 'tomorrow']), default='today')
# @click.option('--state', help='sess_state_code (from causelist-options)')
# @click.option('--district', help='sees_dist_code (from causelist-options)')
# @click.option('--complex', 'complex_code', help='court_complex_code (from causelist-options)')
# @click.option('--est', 'est_code', help='court_est_code (from causelist-options)')
# @click.option('--court-no', 'court_no', help='CL_court_no (from causelist-options)')
# def causelist(date, state, district, complex_code, est_code, court_no):
#     """Download full cause list for given date and optional selectors."""
#     scraper = ECourtsScraper()
#     dt = datetime.date.today() if date == 'today' else datetime.date.today() + datetime.timedelta(days=1)
#     res = scraper.download_cause_list(dt, state=state, district=district, complex_code=complex_code, est_code=est_code, court_no=court_no)
#     click.echo(f'Saved cause list: {res}')


# @cli.command('causelist-options')
# def causelist_options():
#     """List available State/District/Court Complex options from eCourts cause_list page."""
#     scraper = ECourtsScraper()
#     res = scraper.get_cause_list_page()
#     if 'error' in res:
#         click.echo(f"Error fetching options: {res}")
#         return
#     opts = res.get('options', {})
#     for name, items in opts.items():
#         click.echo(f"Select: {name}")
#         for val, txt in items[:50]:
#             click.echo(f"  {val} -> {txt}")


# @cli.command('causelist-download')
# @click.option('--state', help='sess_state_code (from causelist-options)')
# @click.option('--district', help='sees_dist_code (from causelist-options)')
# @click.option('--complex', 'complex_code', required=True, help='court_complex_code (from causelist-options)')
# @click.option('--est', 'est_code', help='court_est_code (from causelist-options)')
# @click.option('--court-no', 'court_no', help='CL_court_no (from causelist-options)')
# @click.option('--date', required=True, help='Date YYYY-MM-DD')
# @click.option('--all-judges', is_flag=True, help='Download all judges PDFs for the complex/date')
# def causelist_download(state, district, complex_code, est_code, court_no, date, all_judges):
#     """Download cause list PDFs for a given court complex and date."""
#     scraper = ECourtsScraper()
#     dt = datetime.datetime.fromisoformat(date).date()
#     page = scraper.download_cause_list(dt, state=state, district=district, complex_code=complex_code, est_code=est_code, court_no=court_no)
#     if isinstance(page, dict) and 'error' in page:
#         click.echo(f"Error fetching cause list: {page}")
#         return
#     html = open(page, 'r', encoding='utf-8').read()
#     links = scraper.find_cause_list_links(html, complex_value=complex_code, date=dt)
#     if 'error' in links:
#         click.echo(f"Error finding links: {links}")
#         return
#     urls = links.get('links', [])
#     if not urls:
#         click.echo('No PDF links found for provided complex/date')
#         return
#     to_download = urls if all_judges else urls[:1]
#     saved = scraper.download_urls(to_download)
#     click.echo(f"Downloaded: {saved}")


# if __name__ == '__main__':
#     cli()





import json
import datetime
import click
import os
from .scraper import ECourtsScraper
from .utils import save_json


@click.group()
def cli():
    """eCourts Scraper CLI - Fetch court case information and cause lists."""
    pass


@cli.command()
@click.option('--cnr', help='Case CNR number')
@click.option('--type', 'case_type', help='Case type (e.g., CRL, CIV)')
@click.option('--number', type=int, help='Case number')
@click.option('--year', type=int, help='Case year')
@click.option('--download-pdf', is_flag=True, help='Download case PDF if available')
@click.option('--today', is_flag=True, help='Check if case is listed today')
@click.option('--tomorrow', is_flag=True, help='Check if case is listed tomorrow')
def check(cnr, case_type, number, year, download_pdf, today, tomorrow):
    """Check case status and retrieve case information.
    
    Examples:
        ecourts-scraper check --cnr "DLHC01-123456-2024"
        ecourts-scraper check --type CRL --number 12345 --year 2024
    """
    
    if today and tomorrow:
        click.echo('❌ Error: --today and --tomorrow are mutually exclusive', err=True)
        return
    
    scraper = ECourtsScraper()
    
    # Determine target date
    target_date = datetime.date.today()
    if tomorrow:
        target_date += datetime.timedelta(days=1)
    
    date_str = target_date.strftime('%d %B %Y')
    click.echo(f'🔍 Fetching case information for {date_str}...\n')
    
    # Fetch case information using direct API
    if cnr:
        click.echo(f'   Searching by CNR: {cnr}')
        res = scraper.check_by_cnr(cnr, download_pdf=download_pdf)
    elif case_type and number and year:
        query = f"{case_type} {number}/{year}"
        click.echo(f'   Searching by case details: {query}')
        res = scraper.check_by_details(case_type, number, year, download_pdf=download_pdf)
    else:
        click.echo('❌ Error: Provide either --cnr OR all of --type/--number/--year', err=True)
        click.echo('\nExamples:')
        click.echo('  ecourts-scraper check --cnr "DLHC01-123456-2024"')
        click.echo('  ecourts-scraper check --type CRL --number 12345 --year 2024')
        return
    
    # Display results
    click.echo('\n' + '='*60)
    
    if isinstance(res, dict) and 'error' in res:
        click.echo('❌ ERROR')
        click.echo('='*60)
        click.echo(f"Error: {res['error']}")
        if 'status' in res:
            click.echo(f"Status Code: {res['status']}")
        if 'url' in res:
            click.echo(f"URL: {res['url']}")
        output_file = 'error_result.json'
    else:
        click.echo('✅ CASE INFORMATION RETRIEVED')
        click.echo('='*60)
        
        # Extract and display key information
        if 'serial' in res:
            click.echo(f"📋 Serial Number: {res['serial']}")
        if 'court' in res:
            click.echo(f"⚖️  Court: {res['court']}")
        
        # Display rows if available
        if 'rows' in res and res['rows']:
            click.echo(f"\n📊 Case Details ({len(res['rows'])} rows):")
            for i, row in enumerate(res['rows'][:5], 1):  # Show first 5 rows
                click.echo(f"   Row {i}: {' | '.join(row)}")
            if len(res['rows']) > 5:
                click.echo(f"   ... and {len(res['rows']) - 5} more rows")
        
        # PDF information
        if 'pdf' in res:
            click.echo(f"\n📄 PDF: {res['pdf']}")
            if download_pdf:
                click.echo('   ✓ PDF downloaded')
        
        # Full JSON output
        click.echo('\n📝 Full Response:')
        click.echo(json.dumps(res, indent=2, ensure_ascii=False))
        
        output_file = f'result_{target_date.isoformat()}.json'
    
    # Save results
    save_json(res, output_file)
    click.echo(f'\n💾 Results saved to: {output_file}')
    click.echo('='*60)


@cli.command('search-causelist')
@click.option('--cnr', help='Case CNR to search for')
@click.option('--query', help='Search query (case number, party name, etc.)')
@click.option('--state', required=True, help='State code (use causelist-options to see list)')
@click.option('--district', required=True, help='District code')
@click.option('--complex', 'complex_code', help='Court complex code (optional)')
@click.option('--date', type=click.Choice(['today', 'tomorrow']), default='today', help='Date to search')
def search_causelist(cnr, query, state, district, complex_code, date):
    """Search for a case in the cause list for a specific court.
    
    Examples:
        ecourts-scraper search-causelist --cnr "DLHC01-123456-2024" --state 8 --district 26
        ecourts-scraper search-causelist --query "12345/2024" --state 8 --district 26
    """
    
    scraper = ECourtsScraper()
    
    # Determine target date
    target_date = datetime.date.today() if date == 'today' else datetime.date.today() + datetime.timedelta(days=1)
    date_str = target_date.strftime('%d %B %Y')
    
    search_term = cnr or query
    if not search_term:
        click.echo('❌ Error: Provide either --cnr or --query', err=True)
        return
    
    click.echo(f'🔍 Searching cause list for {date_str}')
    click.echo(f'   State: {state}, District: {district}')
    if complex_code:
        click.echo(f'   Complex: {complex_code}')
    click.echo(f'   Searching for: {search_term}\n')
    
    # Download cause list
    fname_or_err = scraper.download_cause_list(
        target_date, 
        state=state, 
        district=district, 
        complex_code=complex_code
    )
    
    if isinstance(fname_or_err, dict) and 'error' in fname_or_err:
        click.echo(f"❌ Error downloading cause list: {fname_or_err['error']}")
        return
    
    # Search in the downloaded file
    if not os.path.exists(fname_or_err):
        click.echo(f'❌ File not found: {fname_or_err}')
        return
    
    html = open(fname_or_err, 'r', encoding='utf-8').read()
    
    click.echo('='*60)
    if search_term.lower() in html.lower():
        click.echo(f'✅ FOUND in cause list!')
        click.echo(f'   Search term: {search_term}')
    else:
        click.echo(f'❌ NOT FOUND in cause list')
        click.echo(f'   Search term: {search_term}')
    
    click.echo(f'\n📄 Full cause list saved to: {fname_or_err}')
    click.echo('='*60)


@cli.command()
@click.option('--date', type=click.Choice(['today', 'tomorrow']), default='today')
@click.option('--state', required=True, help='State code (from causelist-options)')
@click.option('--district', required=True, help='District code (from causelist-options)')
@click.option('--complex', 'complex_code', help='Court complex code (from causelist-options)')
@click.option('--est', 'est_code', help='Court establishment code (from causelist-options)')
@click.option('--court-no', 'court_no', help='Court number (from causelist-options)')
def causelist(date, state, district, complex_code, est_code, court_no):
    """Download full cause list for given date and court parameters.
    
    Example:
        ecourts-scraper causelist --state 8 --district 26 --date today
    """
    scraper = ECourtsScraper()
    dt = datetime.date.today() if date == 'today' else datetime.date.today() + datetime.timedelta(days=1)
    
    click.echo(f'📥 Downloading cause list for {dt.strftime("%d %B %Y")}')
    click.echo(f'   State: {state}, District: {district}')
    if complex_code:
        click.echo(f'   Complex: {complex_code}')
    
    res = scraper.download_cause_list(
        dt, 
        state=state, 
        district=district, 
        complex_code=complex_code, 
        est_code=est_code, 
        court_no=court_no
    )
    
    if isinstance(res, dict) and 'error' in res:
        click.echo(f'\n❌ Error: {res["error"]}')
    else:
        click.echo(f'\n✅ Saved cause list to: {res}')


@cli.command('causelist-options')
@click.option('--state', help='State code to get districts for')
@click.option('--district', help='District code to get complexes for')
def causelist_options(state, district):
    """List available State/District/Court Complex options from eCourts.
    
    Examples:
        ecourts-scraper causelist-options                    # List all states
        ecourts-scraper causelist-options --state 8          # List districts for state 8
        ecourts-scraper causelist-options --state 8 --district 26  # List complexes
    """
    scraper = ECourtsScraper()
    
    if state and district:
        # Get complexes
        click.echo(f'🏛️  Fetching court complexes for state {state}, district {district}...\n')
        res = scraper.get_dependent_options(state=state, district=district)
        opts = res.get('options', {})
        
        # Display complexes
        for name, items in opts.items():
            if 'complex' in name.lower():
                click.echo(f'Court Complexes:')
                for val, txt in items:
                    if val and val != '0':
                        click.echo(f'  {val} -> {txt}')
                break
    elif state:
        # Get districts
        click.echo(f'🏛️  Fetching districts for state {state}...\n')
        res = scraper.get_dependent_options(state=state)
        opts = res.get('options', {})
        
        # Display districts
        for name, items in opts.items():
            if 'dist' in name.lower():
                click.echo(f'Districts:')
                for val, txt in items:
                    if val and val != '0':
                        click.echo(f'  {val} -> {txt}')
                break
    else:
        # Get states
        click.echo('🏛️  Fetching states...\n')
        res = scraper.get_cause_list_page()
        if 'error' in res:
            click.echo(f"❌ Error: {res}")
            return
        
        opts = res.get('options', {})
        for name, items in opts.items():
            if 'state' in name.lower():
                click.echo(f'States:')
                for val, txt in items:
                    if val and val != '0':
                        click.echo(f'  {val} -> {txt}')
                break
    
    click.echo('\n💡 Tip: Use these codes with other commands')
    click.echo('   Example: ecourts-scraper causelist --state 8 --district 26')


@cli.command('causelist-download')
@click.option('--state', help='State code')
@click.option('--district', help='District code')
@click.option('--complex', 'complex_code', required=True, help='Court complex code')
@click.option('--est', 'est_code', help='Court establishment code')
@click.option('--court-no', 'court_no', help='Court number')
@click.option('--date', required=True, help='Date in YYYY-MM-DD format')
@click.option('--all-judges', is_flag=True, help='Download PDFs for all judges')
def causelist_download(state, district, complex_code, est_code, court_no, date, all_judges):
    """Download cause list PDFs for a specific court complex and date.
    
    Example:
        ecourts-scraper causelist-download --state 8 --district 26 --complex 1 --date 2025-10-20
    """
    scraper = ECourtsScraper()
    
    try:
        dt = datetime.datetime.fromisoformat(date).date()
    except ValueError:
        click.echo(f'❌ Error: Invalid date format. Use YYYY-MM-DD (e.g., 2025-10-20)', err=True)
        return
    
    click.echo(f'📥 Downloading cause list for {dt.strftime("%d %B %Y")}')
    click.echo(f'   Complex: {complex_code}')
    
    page = scraper.download_cause_list(
        dt, 
        state=state, 
        district=district, 
        complex_code=complex_code, 
        est_code=est_code, 
        court_no=court_no
    )
    
    if isinstance(page, dict) and 'error' in page:
        click.echo(f"\n❌ Error: {page['error']}")
        return
    
    if not os.path.exists(page):
        click.echo(f'\n❌ Error: File not found: {page}')
        return
    
    html = open(page, 'r', encoding='utf-8').read()
    links = scraper.find_cause_list_links(html, complex_value=complex_code, date=dt)
    
    if 'error' in links:
        click.echo(f"\n❌ Error: {links['error']}")
        return
    
    urls = links.get('links', [])
    if not urls:
        click.echo('\n⚠️  No PDF links found for provided complex/date')
        click.echo(f'   HTML saved to: {page}')
        return
    
    click.echo(f'\n✅ Found {len(urls)} PDF link(s)')
    
    to_download = urls if all_judges else urls[:1]
    click.echo(f'📥 Downloading {len(to_download)} PDF(s)...')
    
    saved = scraper.download_urls(to_download)
    
    click.echo('\n📄 Download Results:')
    for item in saved.get('saved', []):
        if 'path' in item:
            click.echo(f"   ✅ {item['path']}")
        elif 'error' in item:
            click.echo(f"   ❌ {item['url']}: {item['error']}")


if __name__ == '__main__':
    cli()
