-- LaTeX only: turn the ESSD statement sections and the appendix of docs/paper/rainier3d_paper.md into the commands of
-- copernicus.cls. A level-1 heading with one of the classes below becomes that command, wrapping the blocks up to
-- the next level-1 heading; {.appendix} emits \appendix before its heading. Other formats are left unchanged.
local statements = {
  codedataavailability = "codedataavailability",
  authorcontribution = "authorcontribution",
  competinginterests = "competinginterests",
  acknowledgements = "acknowledgements",
}

function Pandoc(doc)
  if not FORMAT:match("latex") then
    -- HTML: number the appendix heading by hand ("Appendix A. Data sets")
    for _, b in ipairs(doc.blocks) do
      if b.t == "Header" and b.classes:includes("appendix") then
        b.content = pandoc.Inlines({ pandoc.Str("Appendix A."), pandoc.Space() }) .. b.content
      end
    end
    return doc
  end
  local out, i, blocks = {}, 1, doc.blocks
  while i <= #blocks do
    local b = blocks[i]
    local cmd = nil
    if b.t == "Header" and b.level == 1 then
      for _, c in ipairs(b.classes) do
        cmd = cmd or statements[c]
      end
      if b.classes:includes("appendix") then
        table.insert(out, pandoc.RawBlock("latex", "\\appendix"))
        b.classes = b.classes:filter(function(c) return c ~= "unnumbered" end) -- "Appendix A", tables A1
      end
    end
    if b.t == "Header" and b.identifier == "references" then
      i = i + 1 -- copernicus.cls prints the bibliography with its own heading
    elseif cmd then
      local body = {}
      i = i + 1
      while i <= #blocks and not (blocks[i].t == "Header" and blocks[i].level == 1) do
        table.insert(body, blocks[i])
        i = i + 1
      end
      -- body only (no template), with natbib citations like the rest of the document
      local tex = pandoc.write(pandoc.Pandoc(body), "latex", { cite_method = "natbib" })
      if cmd == "acknowledgements" then
        table.insert(out, pandoc.RawBlock("latex", "\\begin{acknowledgements}\n" .. tex .. "\n\\end{acknowledgements}"))
      else
        table.insert(out, pandoc.RawBlock("latex", "\\" .. cmd .. "{" .. tex .. "}"))
      end
    else
      table.insert(out, b)
      i = i + 1
    end
  end
  doc.blocks = out
  return doc
end
