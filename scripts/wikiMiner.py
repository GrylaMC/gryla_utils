"""
A powerful tool for parsing packets from the Packet section of the minecraft wiki,
originally from wiki.vg.

Since to wiki tends to have many small formatting errors, AI is the most efficient way to process it. 



Wiki url: https://minecraft.wiki/w/Minecraft_Wiki:Protocol_documentation

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




from dotenv import load_dotenv

from typing import *
import os
import requests
from dataclasses import dataclass
import time
from google import genai
from google.genai import types

BASE_URL = "https://minecraft.wiki/api.php?action=query&format=json&prop=revisions&rvslots=*&rvprop=content&revids={}"





SYSTEM_PROMPT = """
You convert Minecraft Wiki packet/protocol definitions into Minecraft Protocol DSL.

ABSOLUTE OUTPUT RULES
- Output ONLY valid Minecraft Protocol DSL text.
- Do NOT output markdown, prose, headings, or code fences.
- If you must explain something, do it ONLY using DSL single-line comments starting with '#'.
- Keep comments minimal: at most 1 comment line per field, and only when required by the rules below.

DSL BASICS
- Whitespace is optional.
- Comments: '#' starts a single-line comment.
- Strings: double quotes ". Strings may span lines; backslash escapes apply.
- Numbers: decimal, hex (0x...), binary (0b...). Decimals like 0.1 allowed.
- Booleans: true / false.
- Lists: [a, b, c]
- Dictionaries: {key: value, ...}
- Objects: Identifier followed by optional (args) and optional attached dictionary and/or attached list:
  Example: Foo(1, 2) {3: 4} [5, 6]
  Example: Foo

REQUIRED OUTPUT SHAPE
- Emit exactly ONE dictionary with exactly ONE entry:
  {
    0xNN: Packet(optional_resource_id?) [ fields... ]
  }
- The dictionary key MUST be the packet ID as hexadecimal with 0x prefix, exactly as on the wiki.
- The dictionary value MUST be a Packet object.
- Packet arguments:
  - Packet("resource_id") ONLY if the wiki explicitly shows a resource id for that protocol/version.
  - Otherwise Packet has no arguments: Packet
- Packet attached list is REQUIRED and contains the ordered list of fields.

FIELDS
- Each field is an object representing its datatype.
- Typical form: Type("Field Name")
- Preserve field order exactly as listed on the wiki.
- Preserve field names exactly as shown on the wiki.
- If the wiki does not provide a name, omit the name argument (Type) unless the datatype requires it.

CHILDREN / NESTED FIELDS (DETERMINISTIC RULE)
Some field types contain child fields ("with children").
Encode children in ONE of these two ways:
1) Argument form: Container(child)
   Use ONLY when the container has exactly 1 child AND the container has no field name on the wiki.
2) Attached list form: Container("Name") [ child1, child2, ... ]
   Use in all other cases (including 2+ children, or container has a name).

UNKNOWN TYPES
- You may ONLY use builtin datatypes listed below.
- If the wiki uses a datatype not in the builtin list, emit:
  TODO("Field Name") # wiki type: <type>, describe briefly
  Put TODO in the correct position in the fields list.

STRING LENGTH RULE
- For String(N), set N only if the wiki explicitly provides it.
- If N is not provided, emit String("Name") and add a short comment:
  String("Name") # max length not specified on wiki

BUILTIN DATATYPES (ALLOWED)
Boolean
Byte
UByte
Short
UShort
Int
Long
Float
Double
String(N optional as second argument)
TextComponent
JsonTextComponent
Identifier
VarInt
VarLong
EntityMetadata
Slot
HashedSlot
NBT
Position
Angle
UUID
BitSet
FixedBitSet(N as second argument)
Optional   # with children; include context in a brief comment if structure is unclear
PrefixedOptional   # with children
Array   # with children; add brief comment describing length/prefix if the wiki indicates it
PrefixedArray   # with children
Enum   # Enum("name", UnderlyingType) {numeric_or_string_key: "label", ...}
EnumSet(N)   # if N missing: EnumSet("Name") # N not specified on wiki
ByteArray
IdOr(x)   # IdOr("Name", OtherType)
IdSet
SoundEvent
ChatType
TeleportFlags
RecipeDisplay
SlotDisplay
ChunkData
LightData
Or(x, y)  ANY TIME YOUT USE AN `Or`, IT MUST BE EXPLAINED IN A COMMENT  # Or(TypeA("A"), TypeB("B"))
GameProfile
ResolvableProfile
DebugSubscriptionEvent
DebugSubscriptionUpdate
LpVec3
Object


EXAMPLE (VALID)
{
  0x02: Packet("login_finished") [
    UUID("UUID"),
    String("Username"),
    PrefixedArray("Properties") [
      String("Name"),
      String("Value"),
      PrefixedOptional(String("Signature"))
    ]
  ]
}

Notes:
`VarInt Enum` turns into `Enum("Name", VarInt){...}`
Comments are for describing how the protocol works, they should be MINIMIZED, not what each feild does (unless told overwise by the above)
Enum values should be lowercase, with spaces between words
When a Packet refers to another datatype that you can see the definition of, inline it.
If you ever feel what you have written might not work in the real world, put the comment "LOW CONFIDENCE: {your confidence rating}%" at the end.

"""
    




def consume_line(x : str) -> Tuple[str, str | None]:
    i = x.find('\n')
    return (x, None) if i == -1 else (x[:i].rstrip(), x[i+1:])

@dataclass
class WikitableCell:
    content : str
    
    isHeader : bool = False
    
    x : int = 1
    y : int = 1

    rowspan : int = 1
    colspan : int = 1


class WikiTable:
    rows : List[List[WikitableCell]]

    width : int
    height : int

    def __init__(self, rows : List[List[WikitableCell]], width : int, height : int):
        self.rows = rows

        self.width = width
        self.height = height
    @classmethod
    def From_txt(cls, txt : str) -> Tuple['WikiTable', str | None]:
        """
        Parse a standered wikitable, where txt is at the start if the wikitable (With allowence for whitespace).
        

        :return: A tuple, the first element being the parsed table obj, the secound being the rest of
                 the string after the table (None if EOS). 
        """

        txt = txt.lstrip()

        rows = []
        curRow = []

        line1, head = consume_line(txt)

        rowspans = []

        assert line1.strip().startswith("{|")
        assert head is not None

        x, y = 0, 0
        width = -1
        height = -1

        while True:
            line, head = consume_line(head)
            line = line.lstrip()

            
            # handle end of tables/files
            if head is None or line.lstrip().startswith("|}"):
                break

            if not len(line):
                continue

            # handle invalid lines
            if line[0] != '!' and line[0] != '|' and len(line.strip()) != 0:
                if len(curRow) == 0:
                   raise ValueError(f"Cannot parse WikiTable due to line: \"{line}\"")
                else:
                    curRow[-1].content += "\n" + line
                continue

            isHeader = line and line[0] == "!"
            line = line[1:].lstrip()
            
            # handle new rows
            if line and line[0] == "-":
                if y == 0 and len(curRow) == 0:
                    # WTF??????
                    continue


                width = max(width, x - 1)

                assert not isHeader
                y += 1
                x = 0

                rows.append(curRow)
                curRow = []

                rowspans = [cell for cell in rowspans if cell.y + cell.rowspan > y]
                continue

            # skip over large cells
            while True:
                for cell in rowspans:
                    isOverlapping = cell.x <= x and cell.y <= y and cell.x + cell.colspan > x and cell.y + cell.rowspan > y
                    if not isOverlapping:
                        continue
                    x += cell.colspan
                    break
                else:
                    break

            # parse arguments
            cellColspan = 1
            cellRowspan = 1
            while True:
                if line.startswith("colspan="):
                    cellColspan = int(line.split('"')[1])
                    line = line[line.find('"') + 1:]
                    line = line[line.find('"') + 1:].lstrip()
                elif line.startswith("rowspan="):
                    cellRowspan = int(line.split('"')[1])
                    line = line[line.find('"') + 1:]
                    line = line[line.find('"') + 1:].lstrip()
                else:
                    break

            if line.startswith('|'):
                line=line[1:].lstrip()
            

            cell = WikitableCell(
                line.rstrip(),
                isHeader,
                x,
                y,
                cellRowspan,
                cellColspan
            )

            if cellRowspan != 1:
                rowspans.append(cell)
            curRow.append(cell)

            x += cellColspan
        # last row edgecase
        rows.append(curRow)



        height = len(rows)

        return WikiTable(
            rows,
            width,
            height
        ), head




    def debug_print(self, colWidth = 5, rowHeight=2):
        """
        Gives you the shape of the table. 

        """
        lines =  [
            
            [' ' for _ in range((self.width + 10) * colWidth) ]
            for _ in range((self.height + 1) * rowHeight)
        ]
        
        for row in self.rows:
            for cell in row:
                ox = cell.x * colWidth
                oy = cell.y * rowHeight
                mx = ox + cell.colspan * colWidth
                my = oy + cell.rowspan * rowHeight
                
                for x in range(ox+1, mx):
                    lines[oy][x] = lines[my][x] = '─'
                for y in range(oy + 1, my):
                    lines[y][ox] = lines[y][mx] = '│'
        print(*("".join(line) for line in lines), sep="\n")
    def subtable(self, x, y, width=-1, height=-1):
        width = width if width != -1 else self.width + 1
        height = height if height != -1 else self.height + 1
        

        rows = [
            [WikitableCell(
                cell.content, cell.isHeader, 
                cell.x - x, cell.y - y,
                cell.rowspan, cell.colspan)
                for cell in row if (
                    cell.x >= x and cell.y >= y and
                    cell.x < x + width and cell.y < y + height
            )]
            for row in self.rows
        ]

        real_width = 0
        for row in rows:
            for cell in row:
                real_width = max(real_width, cell.x + cell.colspan)
        return WikiTable(rows, real_width, len(rows))
        
    def search_headers(self, predicate : Callable[[str], bool]) -> List[WikitableCell]:
        # Headers can only exist on the first row
        return [
            cell for cell in self.rows[0]
            if cell.isHeader and predicate(cell.content)
        ]
        



    def get(self, x : int, y : int) -> None | WikitableCell:
        l = [cell for cell in  self.rows[y] if cell.x == x]
        return None if len(l) == 0 else l[0]


class Wiki:
    name : str
    components : List['Wiki | str']
    def __init__(self, name, components) -> None:
        self.name = name
        self.components = components
    def debug(self) -> str:
        return f"{self.name}[{',\n'.join( (("Content of len: " + str(len(component)) if type(component) is str else component.debug()) for component in self.components))}]".replace("\n", "\n\t")


    @classmethod
    def From_oldid(cls, oldid : int) -> 'Wiki':
        jso = requests.get(BASE_URL.format(oldid )).json()
        wikiContent = jso["query"]["pages"]["290319"]["revisions"][0]["slots"]["main"]["*"]
        
        # WARNING: This is a bad assumption
        segments = wikiContent.split("\n=")
        
        # Initial segment is not part of anything
        components = [segments[0]]
        segments = segments[1:]


        stack = [(-1, Wiki("root", components))]

        for segment in segments:
            # Another HORRIBLE asssumption
            deph = segment.find(' ')
            assert deph != -1

            contentStart = segment.find('\n')
            content = '' if contentStart == -1 else segment[contentStart:].strip() 

            name = segment[deph:]
            name = name.split('=')[0].strip()


            wiki = Wiki(name, [content])


            while deph <= stack[-1][0]:
                stack.pop(-1)

            stack[-1][1].components.append(wiki)
            stack.append((deph, wiki))

        assert type(stack[0][1]) is Wiki, "Wiki stack corruption"
        return stack[0][1]
    
    def get(self, *args) -> 'Wiki':
        if len(args) == 0:
            return self
        for c in self.components:
            if type(c) is Wiki and c.name == args[0]:
                return c.get(*args[1:])
        raise KeyError(args)





if __name__ == "__main__":
    load_dotenv()
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    #
    # llm = Llama.from_pretrained(
    #     repo_id="microsoft/Phi-3-mini-4k-instruct-gguf",
    #     filename="Phi-3-mini-4k-instruct-q4.gguf",
    #     n_ctx=4096,
    #     verbose=False
    # )


    wiki = Wiki.From_oldid(3024144)
    cont = wiki.get("Play", "Clientbound", "Player Info Update").components[0]

    t = time.time()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
        contents="Convert: ```" + cont + "```",
    )

    print(response.text)

    print(time.time() - t)
    # wiki.parse_datatypes()
    # ctx = TypeGenCtx()
    #tbl = WikiTable.From_txt(test)

    #print(ctx.parse_subtable(tbl.subtable(3, 1, width=2), tbl.subtable(5, 1, width=2)).debug_str())

