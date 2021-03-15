import re
from unidecode import unidecode
import argparse
import time


# Helper Function takes URL "reference" keyword and fixed fields then converts them to snort 3
def convertreferencesnort3(urllist):
    # Might need to re-work this to be truely universal, currently relies on surricata fields
    tmp = []
    tmp2 = urllist[0].split(",")
    tmp.append("http_uri")
    tmp.append(";")
    tmp.append("content:\"" + tmp2[1] + "\"")
    tmp.append(urllist[1])
    return tmp


# Helper Function takes Field Agent Keyword and unknown number of associated fields then converts them to Snort 3
def convertuseragentsnort3(snortlist):
    # Count fields so you know how many to add to list
    fieldcount = len(snortlist)
    temp = []
    # Manually write modified header field
    temp.append("http_header: field user-agent")
    temp.append(";")
    temp.append(snortlist[0])
    # Add additional fields if they exist
    if fieldcount > 3:
        for x in range(3, fieldcount):
            temp.append(snortlist[x])
    return temp


# Helper Function takes HTTP_Header Keyword and unknown number of associated fields then converts them to Snort 3
def converthttpheadersnort3(headerlist):
    # Count fields so you know how many to add to list
    fieldcount = len(headerlist)
    temp = []
    # Switch HTTP_Header and CONTENT fields
    temp.append(headerlist[2])
    temp.append(";")
    temp.append(headerlist[0])
    # Add additional fields if they exist
    if fieldcount > 3:
        for x in range(3, fieldcount):
            temp.append(headerlist[3])
    return temp


# Helper Function takes Optional content Key/value pairs and converts them to Snort 3 format
def contentchangersnort3(contentlist):
    for index, item in enumerate(contentlist):
        if index >= 1:
            if re.match(r"^[a-zA-Z0-9]", item[1:]):
                b = contentlist[index].split(":")
                if len(b) > 1:
                    contentlist[index] = b[0] + " " + b[1]
    return contentlist


# Helper Function takes SID and Generates new sequential ID's over 1000000 if they are BELOW, otherwise does nothing
def sidchangersnort3(sidlist):
    global sid_start_selecter

    tmp = sidlist[0].split(":")
    if int(tmp[1]) <= sid_start_selecter:
        sidlist[0] = "sid:" + str(sid_start_selecter)
        sid_start_selecter += 1
    return sidlist


# Helper function selects delimiters based on selected output format
def syntaxselector(state, output3):
    # Based on Output Selector, convert to proper fields for output syntax
    syntax = ""
    if output3 == "SNORT3":
        if not state:
            syntax = ","
        elif state:
            syntax = ";"
        else:
            syntax = "NONE"
    return syntax


# Helper function selects which keywords generate the Rule Index
def indexselector(item2, ingester2):
    # Search for keywords based in Ingest Selector to build index list
    selector = False

    if ingester2 == "SURRICATA":
        for item in SurricataChunkKeywords:
            if item2.find(item) != -1:
                selector = True
    else:
        selector = False
    return selector


# Helper function the lookup table for conversions and calls the conversion functions
def keywordselector(searchitem, lista, output3):
    # Based on Selector, convert to proper fields for output syntax
    if output3 == "SNORT3":
        if searchitem.find("http_user_agent") != -1:
            lista = convertuseragentsnort3(lista)
        elif searchitem.find("reference") != -1:
            lista = convertreferencesnort3(lista)
        elif searchitem.find("http_header") != -1:
            lista = converthttpheadersnort3(lista)
        elif searchitem.find("sid") != -1:
            lista = sidchangersnort3(lista)
        elif searchitem.find("content") != -1:
            lista = contentchangersnort3(lista)
    return lista


# Function Creates Universal list for manipulation
def createintermediatelist(rulefile):
    ruleslist = []
    with open(rulefile, 'r', encoding='utf-8') as file1:
        # Read non-empty lines from file
        lines = [line for line in file1.readlines() if line.strip()]
        for line in lines:
            # remove leading and trailing white space from each line (rule)
            line = line.strip()
            # Strip smart quotes only works on STRINGS so best to do it now...
            line = unidecode(line)
            # Separate each rule component into a list
            line = re.split(' \(|; ', line)
            # Remove Trailing bracket and semicolon
            line[-1] = line[-1][:-2]
            # Sanitize multiple errors
            line = sanitizeingestlist(line)
            # compose rules into single list
            ruleslist.append(line)
    return ruleslist


# This function perform standardization and Sanitization of the ingestlist
def sanitizeingestlist(lista):
    # Fix Arrows
    lista[0] = re.sub(r"(?<=\S)->", " ->", lista[0])

    # Fix Miss-formatted semicolons
    for index, item in enumerate(lista):
        if item.find(";") != -1:
            b = item.split(";")
            lista[index]=b[0]
            lista.insert(index + 1, b[1])

    # Fix skipped white space
    for index, item in enumerate(lista):
        lista[index] = lista[index].strip()

    return lista


# This function creates an index for each rule in the list given to it
def generateruleindex(rulelist2, ingester):
    indexlist2 = []
    statecheck = False
    # Search rule keywords and create index for "chunking"
    for index3, item3 in enumerate(rulelist2):
        indexlist2.append([])
        for item2 in item3:
            statecheck = indexselector(item2, ingester)
            if statecheck:
                indexlist2[index3].append(True)
            else:
                indexlist2[index3].append(False)
            statecheck = False
    return indexlist2


# This function enumerates the INGEST rules and converts them to OUTPUT syntax
def convertlist(indexlist3, ruleslist3, output2):
    convertedlist = []
    templist = []

    # "For each rule" perform chunking and conversion
    for index, item in enumerate(indexlist3):
        convertedlist.append([])
        # First field of rule always behaves differently.... "alert....("
        templist.append(ruleslist3[index][0])
        templist.append(" (")
        for item3 in templist:
            convertedlist[index].append(item3)
        templist = []
        # Add first non-alert field to the temporary list
        templist.append(ruleslist3[index][1])
        # Iterate over each of remaining items in the rule
        for index4, item4 in enumerate(indexlist3[index][2:], 2):
            # print(indexlist3[index][2:])
            # If indexlist is True then dump current chunk and convert list, start again
            if indexlist3[index][index4]:
                templist.append(syntaxselector(indexlist3[index][index4], output2))
                for index2, item2 in enumerate(templist):
                    templist = keywordselector(item2, templist, output2)
                for item3 in templist:
                    convertedlist[index].append(item3)
                templist = []
                templist.append(ruleslist3[index][index4])
            # Otherwise add to chunk
            else:
                templist.append(syntaxselector(indexlist3[index][index4], output2))
                templist.append(ruleslist3[index][index4])
        templist.append(syntaxselector(True, output2))
        templist.append(")")
        for item3 in templist:
            convertedlist[index].append(item3)
        templist = []
    # return Full list of rules
    return convertedlist


# This function takes the final converted rules and writes them to a file
def writerulestofile(lista, outfilename):
    with open(outfilename, 'w', encoding='utf-8') as file1:
        # Spacing Selector
        for index, item in enumerate(lista):
            for index2, item2 in enumerate(lista[index]):
                if index2 > 2:
                    if re.match(r"^[a-zA-Z0-9]", item2[1:]):
                        lista[index][index2] = " " + item2
        # For each "rule" (row) in List
        for item in lista:
            # ...Output all items in a joined line
            file1.write(''.join(item))
            # ...Then add a carriage return
            file1.write('\n')


def main(sid, ingest, output, infile, outfile):
    global sid_start_selecter
    sid_start_selecter = sid

    # Create Rule List from Ingest Set
    start_list = createintermediatelist(infile)
    # Create Index for Key words (based in Ingest Selector)
    index_list = generateruleindex(start_list, ingest)
    # Generate the Base Output List
    base_output_list = convertlist(index_list, start_list, output)
    # User Emitter to generate final syntax rules
    writerulestofile(base_output_list, outfile)


SurricataChunkKeywords = ["ssl", "alert", "msg:", "flow:", "content:", "reference:", "classtype:", "metadata:",
                          "sid", "rev"]


if __name__ == '__main__':
    # TODO: Add McAfee, Forescout, Fortinet, Snort2

    # Initialize Argument Parser
    parser = argparse.ArgumentParser(description="Program Accepts Selected rule input and converts to selected output \
    rule type.")
    parser.add_argument("input_file", type=str, help="Full path to Source File")
    parser.add_argument("output_file", type=str, help="Full path for Output File")
    parser.add_argument("--source_rule_type", type=str, help="Source Rule OPTIONS: Surricata", default="SURRICATA")
    parser.add_argument("--output_rule_type", type=str, help="Output Rule OPTIONS: Snort3", default="SNORT3")
    parser.add_argument("--SID", type=int, help="Starting SID value for Snort rules", default="1000001")
    args = parser.parse_args()

    start = time.time()

    main(args.SID, args.source_rule_type, args.output_rule_type, args.input_file, args.output_file)

    end = time.time()
    print(f"Runtime of the program is {end - start}")
