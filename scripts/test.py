from scrape_urls_google import get_dashboards_from_sites


def test_get_dashboards_from_sites():
    dashboards = get_dashboards_from_sites("marketing analytics", limit=20)
    print(len(dashboards))
    print(dashboards)

if __name__ == "__main__":
    test_get_dashboards_from_sites()
