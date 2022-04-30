# mdx-tablespan

Row and column spanning for Markdown tables 

An extension adapted for python-markdown 3 from the great [Griffon26/mdx_spantables](https://github.com/Griffon26/mdx_spantables) repo which had some import issues due to naming changes in Markdown 3. The syntax is the same, find more examples in that repo. :smiley: 

```markdown
| Column 1 | Column 2 | | Column 3 |
| --- | --- | --- |
| row 1, col 1 | rows 1-2, cols 2-3 ||
| row 2, col 1 |_ ||
| rows 3-5, col 1 | row 3, cols 2-3 ||
| | row 4, col 2 | rows 4-5, col 3 |
|_ | row 5, col 2 |_ |
```
