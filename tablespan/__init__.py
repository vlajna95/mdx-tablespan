import logging
from markdown.extensions import Extension
from markdown.blockprocessors import BlockProcessor
from markdown.inlinepatterns import Pattern, BACKTICK_RE
import xml.etree.ElementTree as etree
import re


class SpanTableProcessor(BlockProcessor):
	""" Process Tables. """
	
	def __init__(self, md, caption_mark=";"):
		self.md = md
		self.caption_mark = caption_mark
	
	def test(self, parent, block):
		rows = block.split("\n")
		return (len(rows) > 2 and "|" in rows[0]) # and "|" in rows[1] and "-" in rows[1] and rows[1].strip()[0] in ["|", ":", "-"])
	
	def is_end_of_rowspan(self, td):
		return ((td != None) and (td.text.startswith("_") or td.text.endswith("_")) and (td.text.strip("_ ") == ""))
	
	def apply_rowspans(self, tbody):
		table_cells = {}
		rows = tbody.findall("tr")
		max_cols = 0
		max_rows = len(rows)
		for y, tr in enumerate(rows):
			cols = tr.findall("td")
			x = 0
			for td in cols:
				colspan_str = td.get("colspan")
				colspan = int(colspan_str) if colspan_str else 1
				# Insert the td together with its parent
				table_cells[(x, y)] = (tr, td)
				x += colspan
			max_cols = max(max_cols, x)
		for x in range(max_cols):
			possible_cells_in_rowspan = 0
			current_colspan = None
			for y in range(max_rows):
				_, td = table_cells.get((x, y), (None, None))
				if td == None:
					possible_cells_in_rowspan = 0
				else:
					colspan = td.get("colspan")
					if colspan != current_colspan:
						current_colspan = colspan
						possible_cells_in_rowspan = 0
					if not td.text:
						possible_cells_in_rowspan += 1
					elif self.is_end_of_rowspan(td):
						td.text = ""
						possible_cells_in_rowspan += 1
						first_cell_of_rowspan_y = y - (possible_cells_in_rowspan - 1)
						for del_y in range(y, first_cell_of_rowspan_y, -1):
							tr, td = table_cells.get((x, del_y))
							tr.remove(td)
						_, first_cell = table_cells.get((x, first_cell_of_rowspan_y))
						first_cell.set("rowspan", str(possible_cells_in_rowspan))
						possible_cells_in_rowspan = 0
					else:
						possible_cells_in_rowspan = 1
	
	def run(self, parent, blocks):
		""" Parse a table block and build table. """
		block = blocks.pop(0).split("\n")
		sep_re = r"^\|\s*\-+\s*(\|\s*\-+\s*)+\|$"
		sep_index = next((i for i, l in enumerate(block) if re.search(sep_re, l)), None) # block.index(sep_re)
		separator = block[sep_index].strip() # block[1].strip()
		header = block[0:sep_index] # block[0].strip()
		rows = [] if len(block) < 3 else block[sep_index+1:]
		# add a table caption if the last row starts with the caption_mark string
		caption = ""
		if rows[-1].startswith(self.caption_mark):
			caption = rows.pop(-1)
			# logging.info(f"{caption[caption.find(self.caption_mark):]} - {len(rows)} row(s) left.")
		# Get format type (bordered by pipes or not)
		border = False
		if header[0].startswith("|"):
			border = True
		# Get alignment of columns
		align = []
		for c in self._split_row(separator, border):
			if c.startswith(":") and c.endswith(":"):
				align.append("center")
			elif c.startswith(":"):
				align.append("left")
			elif c.endswith(":"):
				align.append("right")
			else:
				align.append(None)
		# Build table
		table = etree.SubElement(parent, "table")
		if caption != "":
			table_caption = etree.SubElement(table, "caption")
			table_caption.text = caption.replace(self.caption_mark, "").strip(" ")
		thead = etree.SubElement(table, "thead")
		for head_row in header:
			self._build_row(head_row.strip(), thead, align, border)
		tbody = etree.SubElement(table, "tbody")
		for row in rows:
			self._build_row(row.strip(), tbody, align, border)
		self.apply_rowspans(tbody)
	
	def _build_row(self, row, parent, align, border):
		""" Given a row of text, build table cells. """
		tr = etree.SubElement(parent, "tr")
		tag = "th" if parent.tag == "thead" else "td"
		cells = self._split_row(row, border)
		c = None
		# We use align here rather than cells to ensure every row contains the same number of columns.
		for i, a in enumerate(align):
			# After this None indicates that the cell before it should span this column and "" indicates an cell without content
			try:
				text = cells[i]
				if text == "":
					text = None
			except IndexError:  # pragma: no cover
				text = ""
			# No text after split indicates colspan
			if text == None:
				if c is not None:
					colspan_str = c.get("colspan")
					colspan = int(colspan_str) if colspan_str else 1
					c.set("colspan", str(colspan+1))
				else:
					# if this is the first cell, then fall back to creating an empty cell
					text = ""
			if text != None:
				c = etree.SubElement(tr, tag)
				c.text = text.strip()
			if a:
				c.set("align", a)
	
	def _split_row(self, row, border):
		""" split a row of text into list of cells. """
		if border:
			if row.startswith("|"):
				row = row[1:]
			if row.endswith("|"):
				row = row[:-1]
		return self._split(row, "|")
	
	def _split(self, row, marker):
		""" split a row of text with some code into a list of cells. """
		if self._row_has_unpaired_backticks(row):
			# fallback on old behaviour
			return row.split(marker)
		# modify the backtick pattern to only match at the beginning of the search string
		backtick_pattern = Pattern("^" + BACKTICK_RE)
		elements = []
		current = ""
		i = 0
		while i < len(row):
			letter = row[i]
			if letter == marker:
				elements.append(current)
				current = ""
			else:
				m = backtick_pattern.getCompiledRegExp().match(row[i:])
				if not m:
					current += letter
				else:
					groups = m.groups()
					delim = groups[1]  # the code block delimiter (ie 1 or more backticks)
					row_contents = groups[2]  # the text contained inside the code block
					i += match.start(4) - 1  # jump pointer to the beginning of the rest of the text (group #4)
					element = delim + row_contents + delim  # reinsert backticks
					current += element
			i += 1
		elements.append(current)
		return elements
	
	def _row_has_unpaired_backticks(self, row):
		count_total_backtick = row.count("`")
		count_escaped_backtick = row.count("\\`")
		count_backtick = count_total_backtick - count_escaped_backtick
		# odd number of backticks, we won't be able to build correct code blocks
		return count_backtick & 1


class TableSpanExtension(Extension):
	""" Add tables to Markdown. """
	
	def __init__(self, **kwargs):
		self.config = {
			"caption_mark": [";", "The string to be used as a mark for the row containing the table caption"],
		}
		super(TableSpanExtension, self).__init__(**kwargs)
	
	def extendMarkdown(self, md):
		"""Register an instance of SpanTableProcessor in BlockParsers."""
		try:
			md.parser.blockprocessors.deregister("table")
		except Exception as e:
			pass
		finally:
			md.parser.blockprocessors.register(SpanTableProcessor(md.parser, caption_mark=self.getConfig("caption_mark")), "table", 75)


def makeExtension(*args, **kwargs):
	return TableSpanExtension(*args, **kwargs)
