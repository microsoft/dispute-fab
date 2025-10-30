let
  Source = Excel.Workbook(Web.Contents("https://YOURSHAREPOINT.sharepoint.com/personal/YOURACCOUNT/Documents/Apps/Microsoft Power Query/Uploaded Files/ReasonCodeLookup.xlsx"), null, true),
  #"Navigation 1" = Source{[Item = "Sheet1", Kind = "Sheet"]}[Data],
  #"Promoted headers" = Table.PromoteHeaders(#"Navigation 1", [PromoteAllScalars = true]),
  #"Changed column type" = Table.TransformColumnTypes(#"Promoted headers", {{"Reason Code", Int64.Type}, {"Description", type text}, {"Comment", type text}, {"Rank", Int64.Type}, {"hvsq key", type text}, {"gpkdke key", type text}})
in
  #"Changed column type"