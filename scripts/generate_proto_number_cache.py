"""
Regenerates data/protoNums.json based on the wiki

Copyright (C) 2025 - PsychedelicPalimpsest


This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import requests, json, os
from wiki_miner import *
from bs4 import BeautifulSoup


def main():
    sp = BeautifulSoup(
        requests.get(
            "https://minecraft.wiki/api.php?action=parse&page=Minecraft_Wiki:Projects/wiki.vg_merge/Protocol_version_numbers&format=json"
        ).json()["parse"]["text"]["*"]
    )

    table = sp.find("table").find("tbody")
    rowspan_mode = None

    out = []


    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) == 0:
            continue

        if len(cells) == 3 and rowspan_mode is None and "rowspan" in cells[1].attrs:
            rowspan_mode = [int(cells[1]["rowspan"]),  cells[1], cells[2]]

        if rowspan_mode:
            cells = (cells[0], rowspan_mode[1], rowspan_mode[2])
            rowspan_mode[0] -= 1
            if rowspan_mode[0] <= 0:
                rowspan_mode = None
        

        if len(cells) == 3 and (a:=cells[2].find("a")) is not None:
            if a.text != "page":
                continue
            
            out.append((cells[0].text.strip(), cells[1].text.strip(), a.get('href')))


    f = open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/protoNums.json")
        , "w")
    
    f.write(json.dumps(out, indent=2))
    f.close()


    print("Saved results to protoNums.json")




if __name__ == "__main__":
    main()
