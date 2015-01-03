#!/usr/bin/env python3

import sys
import re
import itertools
import urllib.parse

import lxml.etree as etree

import pyopenmensa.feed


def sub_whitespace(text):
    return re.sub("\s+", " ", text)


def meals_uri(mensa_name):
    base = 'http://www.studentenwerk-goettingen.de/speiseplan.html?'
    params = {
        'no_cache': 1,
        'day': 7,
        'selectmensa': mensa_name,
        'push': 0
    }
    this_week = base + urllib.parse.urlencode(params)
    params['push'] = 1
    next_week = base + urllib.parse.urlencode(params)
    return this_week, next_week


def get_prices(source, parser):
    """Returns a dict with meal type as key and list of prices as value."""
    tree = etree.parse(source, parser)
    tables = tree.xpath("//table")
    if not tables:
        return {}
    prices = {}
    for row in tables[0].getchildren():
        cols = [sub_whitespace(x.text) for x in row if x.text is not None]
        if not cols:
            continue
        meal_type = cols.pop(0)
        if not meal_type.isspace() and cols and not cols[0].isspace():
            prices[meal_type] = cols
    return prices


def get_meals(mensa, uri, parser):
    tree = etree.parse(uri, parser)
    for day in tree.xpath("//div[@class='speise-tblhead']"):
        # fix for M&Atilde;&curren;rz ...
        date = re.sub('M..rz', 'März', day.text)
        date = pyopenmensa.feed.extractDate(date)

        table = day.getnext()
        for tr in table.iterchildren():
            cat = tr.xpath(".//span[@class='ext_sits_preis']")
            if not cat:
                continue
            c = cat[0].text

            # fix <br> line break in first column
            for br in cat[0].xpath(".//br"):
                c += " " + br.tail
            cat = c

            # fix nordmensa inconsistency between price list and menu
            if mensa == 'Nordmensa':
                if "1" in cat:
                    cat = "Stamm I Vegetarisch"
                elif "2" in cat:
                    cat = "Stamm II"
                elif "3" in cat:
                    cat = "Stamm III"

            meal = tr.xpath(".//span[@class='ext_sits_essen']/strong")
            if not meal or meal[0].text is None:
                continue
            meal = meal[0].text + " " + meal[0].tail.strip()

            # remove notes about special ingredients
            # e.g.
            #     "Curryfleischwurst (2,3,8) vom Schwein"
            #  -> "Curryfleischwurst vom Schwein"
            meal = re.sub(r' \(\d+(,\d+)*\)', '', meal)

            yield (date, cat, meal)


def mensa_feed(mensa, this_week_uri, next_week_uri, prices_uri,
               roles=('student', 'employee', 'other')):
    parser = etree.HTMLParser(encoding='utf-8', no_network=False)
    prices = get_prices(prices_uri, parser)
    builder = pyopenmensa.feed.LazyBuilder()
    meals = itertools.chain(get_meals(mensa, this_week_uri, parser),
                            get_meals(mensa, next_week_uri, parser))
    for date, cat, meal in meals:
        p = prices.get(cat)
        builder.addMeal(date, cat, meal, prices=p, roles=roles)

    return builder.toXMLFeed()


if __name__ == '__main__':
    mensae = {
        'z': ('Zentralmensa', 'preise_zm.html'),
        'n': ('Nordmensa', 'preise-nm.html'),
        't': ('Mensa am turm', 'preise-mat.html'),
        'i': ('Mensa Italia', 'preise-mi.html'),
        'h': ('Bistro HAWK', 'preise-hawk.html')
        }

    name, prices = mensae[sys.argv[1]]
    prices = 'http://studentenwerk-goettingen.de/' + prices
    this_week, next_week = meals_uri(name)
    print(mensa_feed(name, this_week, next_week, prices))
