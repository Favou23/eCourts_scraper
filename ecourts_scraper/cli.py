import json
import datetime
import click
from .scraper import ECourtsScraper
from .utils import save_json


@click.group()
def cli():
    pass


@cli.command()
@click.option('--cnr', help='Case CNR number')
@click.option('--type', 'case_type', help='Case type')
@click.option('--number', type=int, help='Case number')
@click.option('--year', type=int, help='Case year')
@click.option('--download-pdf', is_flag=True, help='Download case PDF if available')
@click.option('--today', is_flag=True, help='Assume listing date is today (alias)')
@click.option('--tomorrow', is_flag=True, help='Assume listing date is tomorrow (alias)')
@click.option('--when', type=click.Choice(['today','tomorrow']), default='today', help='Which date to check listings for')
def check(cnr, case_type, number, year, download_pdf, today, tomorrow, when):
    """Check whether a case is listed today or tomorrow."""
    # determine target date
    if today and tomorrow:
        click.echo('--today and --tomorrow are mutually exclusive')
        return
    if today:
        when = 'today'
    if tomorrow:
        when = 'tomorrow'

    scraper = ECourtsScraper()
    # If user provided causelist-like check (when=today/tomorrow), try searching cause list
    target_date = datetime.date.today() if when == 'today' else datetime.date.today() + datetime.timedelta(days=1)
    if cnr:
        # try searching the cause list for CNR (best-effort)
        res = scraper.search_case_in_cause_list(target_date, cnr)
    else:
        if not (case_type and number and year):
            click.echo('Provide either --cnr or --type/--number/--year')
            return
        # Build a textual query and search cause list
        q = f"{case_type} {number} {year}"
        res = scraper.search_case_in_cause_list(target_date, q)

    click.echo(json.dumps(res, indent=2, ensure_ascii=False))
    save_json(res, f'result_{target_date.isoformat()}.json')


@cli.command()
@click.option('--date', type=click.Choice(['today', 'tomorrow']), default='today')
@click.option('--state', help='sess_state_code (from causelist-options)')
@click.option('--district', help='sees_dist_code (from causelist-options)')
@click.option('--complex', 'complex_code', help='court_complex_code (from causelist-options)')
@click.option('--est', 'est_code', help='court_est_code (from causelist-options)')
@click.option('--court-no', 'court_no', help='CL_court_no (from causelist-options)')
def causelist(date, state, district, complex_code, est_code, court_no):
    """Download full cause list for given date and optional selectors."""
    scraper = ECourtsScraper()
    dt = datetime.date.today() if date == 'today' else datetime.date.today() + datetime.timedelta(days=1)
    res = scraper.download_cause_list(dt, state=state, district=district, complex_code=complex_code, est_code=est_code, court_no=court_no)
    click.echo(f'Saved cause list: {res}')


@cli.command('causelist-options')
def causelist_options():
    """List available State/District/Court Complex options from eCourts cause_list page."""
    scraper = ECourtsScraper()
    res = scraper.get_cause_list_page()
    if 'error' in res:
        click.echo(f"Error fetching options: {res}")
        return
    opts = res.get('options', {})
    for name, items in opts.items():
        click.echo(f"Select: {name}")
        for val, txt in items[:50]:
            click.echo(f"  {val} -> {txt}")


@cli.command('causelist-download')
@click.option('--state', help='sess_state_code (from causelist-options)')
@click.option('--district', help='sees_dist_code (from causelist-options)')
@click.option('--complex', 'complex_code', required=True, help='court_complex_code (from causelist-options)')
@click.option('--est', 'est_code', help='court_est_code (from causelist-options)')
@click.option('--court-no', 'court_no', help='CL_court_no (from causelist-options)')
@click.option('--date', required=True, help='Date YYYY-MM-DD')
@click.option('--all-judges', is_flag=True, help='Download all judges PDFs for the complex/date')
def causelist_download(state, district, complex_code, est_code, court_no, date, all_judges):
    """Download cause list PDFs for a given court complex and date."""
    scraper = ECourtsScraper()
    dt = datetime.datetime.fromisoformat(date).date()
    # download cause list HTML with the provided selectors
    page = scraper.download_cause_list(dt, state=state, district=district, complex_code=complex_code, est_code=est_code, court_no=court_no)
    if isinstance(page, dict) and 'error' in page:
        click.echo(f"Error fetching cause list: {page}")
        return
    # now read the saved HTML file
    html = open(page, 'r', encoding='utf-8').read()
    links = scraper.find_cause_list_links(html, complex_value=complex_code, date=dt)
    if 'error' in links:
        click.echo(f"Error finding links: {links}")
        return
    urls = links.get('links', [])
    if not urls:
        click.echo('No PDF links found for provided complex/date')
        return
    to_download = urls if all_judges else urls[:1]
    saved = scraper.download_urls(to_download)
    click.echo(f"Downloaded: {saved}")


if __name__ == '__main__':
    cli()
