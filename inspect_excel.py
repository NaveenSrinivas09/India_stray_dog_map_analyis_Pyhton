import pandas as pd

path = 'data/FinalDistrictWiseStrayCattleDog.xlsx'
print('Opening:', path)
xls = pd.ExcelFile(path)
print('Sheets:', xls.sheet_names)
for sh in xls.sheet_names:
	print('\n=== Sheet:', sh, '===')
	df = xls.parse(sh)
	print('Columns:', list(map(str, df.columns)))
	print(df.head(10).to_string(index=False)) 