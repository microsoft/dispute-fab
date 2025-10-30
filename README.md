Setup Requirements

1. A Fabric workspace with Fabric capacity connected to it.
2. A sharepoint site

Setup Steps
1. Create a lakehouse in your workspace
2. Upload ReasonCodeLookup.xlsx and your datafeeds to your sharepoint site
3. Create dataflows gen 2 based on the power query code.  Edit any xlsx paths to match your files and sharepoint paths. 
4. Ensure the final step of your dataflows adds a step to save the results to your empty lakehouse.  First run will create the data tables
5. Create the date table based on your date table, or use the jupiter notebook to create a sample one
6. Create Data Agents using the Agent and Data instructions as well as Sample Queries.
