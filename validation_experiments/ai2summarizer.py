# Maja Svanberg
# AI2 summarizer
# Code adapted from jail.py

import os
import os.path
import json
import zipfile
import xml.etree.ElementTree as ET
import re

def allProjectsToJSONFiles(userDir, numUsers):
    '''assumes cwd contains dir, that contains projects (in .aia, .zip, or as dir)'''
    listOfAllProjects = findProjectDirs(userDir, numUsers)
    for project in listOfAllProjects:
        projectToJSONFile(project)
        if os.path.exists(project.split('.')[0]) and project.split('.')[1] == 'zip':
            os.remove(project)


def findProjectDirs(dirName, numUsers):
    projects = []
    for user in os.listdir(dirName)[:numUsers]:
        user = os.path.join(dirName, user)
        if os.path.isdir(user):
          for project in os.listdir(user):
              projectPath = os.path.join(user, project)
              if os.path.isdir(projectPath):
                  projects.append(zipdir(projectPath, projectPath + '.zip'))
              elif projectPath.endswith('.aia') or projectPath.endswith('.zip'):
                  projects.append(projectPath)
    return projects

def zipdir(path, ziph):
    zf = zipfile.ZipFile(ziph, "w")
    for root, dirs, files in os.walk(path):
        for file in files:
            zf.write(os.path.join(root, file))
    zf.close()
    return ziph

def projectToJSONFile(projectPath):
    jsonProjectFileName = projectPath.split('.')[0] + '_summary.json'
    jsonProject = projectToJSON(projectPath)
    with open (jsonProjectFileName, 'w') as outFile:
        outFile.write(json.dumps(jsonProject,
                             sort_keys=True,
                             indent=2, separators=(',', ':')))

def projectToJSON(projectPath):
    summary = {}
    if not projectPath.endswith('zip') and not projectPath.endswith('.aia'):
        raise Exception("project is not .aia or  .zip")
    with zipfile.ZipFile(projectPath, 'r') as myZip:
        summary['**Project Name'] = findName(myZip)
        listOfScreens = findScreenNames(myZip)
        summary['*Number of Screens'] = len(listOfScreens)
        for screen in listOfScreens:
            screenInfo = screenToJSON(myZip, screen, projectPath)
            summary[str(screen)] = screenInfo
        summary['*Media Assets'] = findMedia(myZip)
    return summary


'''Given a Python zip file and a pathless filename (no slashes), extract the lines from filename,             
   regardless of path. E.g., Screen1.bky should work if archive name is Screen1.bky                                                                                  or src/appinventor/ai_fturbak/PROMOTO_IncreaseButton/Screen1.bky. 
   it also strips the file from '&'s and '>'  '''
def linesFromZippedFile(zippedFile, pathlessFilename):
    if "/" in pathlessFilename:
        raise RuntimeError("linesFromZippedFile -- filename should not contain slash: " + pathlessFilename)
    names = zippedFile.namelist()
    if pathlessFilename in names:
        fullFilename = pathlessFilename
    else:
        matches = filter(lambda name: name.endswith("/" + pathlessFilename), names)
    if len(matches) == 1:
        fullFilename = matches[0]
    elif len(matches) == 0:
        raise RuntimeError("linesFromZippedFile -- no match for file named: " + pathlessFilename)
    else:
        raise RuntimeError("linesFromZippedFile -- multiple matches for file named: "
                         + pathlessFilename
                         + "[" + ",".join(matches) + "]")
    return zippedFile.open(fullFilename).readlines()

def findName(zippedFile): 
    pp = linesFromZippedFile(zippedFile, 'project.properties') 
    return  pp[1][:-1].split('=')[1]

def findMedia(zippedFile):
    listOfMedia = []
    for file in zippedFile.namelist():
        if '.' in str(file):
            if file.split('.')[1] != 'properties' and file.split('.')[1] != 'bky' and file.split('.')[1] != 'yail' and file.split('.')[1] != 'scm':
                listOfMedia.append(file.split('/')[-1])
    return listOfMedia

def findScreenNames(zippedFile): 
    names = zippedFile.namelist()
    screens = []
    for file in names:
        if str(file)[-4:] == '.bky':
            screens.append(str(file.split('/')[-1])[:-4])
    return screens

def screenToJSON(zippedFile, screenName, projectPath):
    components = scmToComponents(zippedFile, screenName + '.scm')
    bky = bkyToSummary(zippedFile, screenName + '.bky', projectPath)
    return {'Components': components, 'Blocks': bky}

def scmToComponents(zippedFile, scmFileName):
    scmLines = linesFromZippedFile(zippedFile, scmFileName)
    if (len(scmLines) == 4
        and scmLines[0].strip() == '#|'
        and scmLines[1].strip() == '$JSON'
        and scmLines[3].strip() == '|#'):
        data = json.loads(scmLines[2])
    strings = []
    components = {}
    if u'$Components' not in data[u'Properties'].keys():
        return 'NO COMPONENTS'
    else:
        for component in data[u'Properties'][u'$Components']:
            if component[u'$Type'] in components:
                components[component['$Type']] += 1
            else: 
                components[component['$Type']] = 1
            if u'Text' in component.keys():
                strings.append(component[u'Text'])
    return {'Number of Components': len(components), 'Type and Frequency': components, 'Strings': strings}

def elementTreeFromLines(lines, projectPath):
    """ This function is designed to handle the following bad case: <xml xmlns="http://www.w3.org/1999/xhtml">
    for each file parse the xml to have a tree to run the stats collection on
    assumes if a namespace exists that it's only affecting the xml tag which is assumed to be the first tag"""
    # lines = open(filename, "r").readlines()                                     
    try:
        firstline = lines[0] #we are assuming that firstline looks like: <xml...>... we would like it to be: <xml>...                                                             
        if firstline[0:4] != "<xml":
            return ET.fromstringlist(['<xml></xml>'])
        else:
            closeindex = firstline.find(">")
            firstline = "<xml>" + firstline[closeindex + 1:]
            lines[0] = firstline
     #Invariant: lines[0] == "<xml>..." there should be no need to deal with namespace issues now
            return ET.fromstringlist(lines)
    except (IndexError, ET.ParseError):
        print (str(projectPath) + " bky malformed")
        return ET.fromstringlist(['<MALFORMED></MALFORMED>'])

def bkyToSummary(zippedFile, bkyFileName, projectPath):
  bkyLines = linesFromZippedFile(zippedFile, bkyFileName)
  rootElt = elementTreeFromLines(bkyLines, projectPath)
  if rootElt.tag == 'MALFORMED':
      return 'MALFORMED BKYFILE'
  elif not rootElt.tag == 'xml':
      raise RuntimeError('bkyToSummary: Root of bky file is not xml but ' + rootElt.tag)
  else:
      listOfBlocks = []
      listOfOrphans = []
      top  = []
      if len(rootElt) < 1:
          return 'NO BLOCKS'
      for child in rootElt:
          if child.tag == 'block':
              top.append(child.attrib['type'])
              type = child.attrib['type']
              component_selector = False
              for grandchild in child:
                  if grandchild.tag == 'title' or grandchild.tag =='field':
                      if grandchild.attrib['name'] == 'COMPONENT_SELECTOR':
                          component_selector = True
              if type == 'component_event' or type  == 'global_declaration' or type == 'procedures_defnoreturn' or type == 'procedures_defreturn' or type == 'procedures_callnoreturn' or type == 'procedures_callreturn' or type[:-4] == 'lexical_variable':
                  listOfBlocks += findBlockInfo(child)
              elif component_selector:
                  listOfBlocks += findBlockInfo(child)
              else:
                  listOfOrphans += findBlockInfo(child)
      if len(listOfBlocks) == 0:
          blocks = 'NO ACTIVE BLOCKS'
      else:
          blocks = formatLists(listOfBlocks)
      if len(listOfOrphans) == 0:
          orphans = 'NO ORPHAN BLOCKS'
      else:
          orphans = formatLists(listOfOrphans)
      return {'*Top Level Blocks': sortToDict(top), 'Active Blocks': blocks, 'Orphan Blocks': orphans}

def formatLists(inputList):
      blockDict = {}
      blockDict['Types'] = []
      blockDict['*Number of Blocks'] = len(inputList)
      blockDict['Procedure Names'] = []
      blockDict['Procedure Parameter Names'] = []
      blockDict['Global Variable Names'] = []
      blockDict['Local Variable Names'] = []
      blockDict['Strings'] = []
      for dict in inputList:
          for key in dict:
              if key == 'Type':
                  blockDict['Types'].append(dict[key])
              else:
                  blockDict[key] += dict[key]
      for key in blockDict:
          if key != '*Number of Blocks':
              blockDict[key] = sortToDict(blockDict[key])
      return blockDict

def sortToDict(list):
    output = {}
    for elt in list:
        if elt not in output.keys():
            output[elt] = 1
        else:
            output[elt] += 1
    return output

def findBlockInfo(xmlBlock):
    blockDict = {}
    type = xmlBlock.attrib['type']
    blockDict['Type'] = type
    blockDict['Procedure Names'] = []
    blockDict['Procedure Parameter Names'] = []
    blockDict['Global Variable Names'] = []
    blockDict['Local Variable Names'] = []
    blockDict['Strings'] = []
    subBlocks = []
    if type  == 'procedures_defnoreturn' or type == 'procedures_defreturn' or type == 'procedures_callnoreturn' or type == 'procedures_callreturn':
        for child in xmlBlock:
            if child.tag == 'title' or child.tag == 'field':
                blockDict['Procedure Names'] = [child.text]
            for param in child:
                if param.tag == 'arg':
                    blockDict['Procedure Parameter Names'].append(param.attrib['name'])
    if type  == 'global_declaration' or type == 'lexical_variable_get' or  type == 'lexical_variable_set':
        for child in xmlBlock:
            if child.tag == 'field' or child.tag == 'title':
                blockDict['Global Variable Names'].append(child.text)
    if type == 'local_declaration_statement' or type == 'local_declaration_expression':
        for child in xmlBlock:
            if child.tag == 'title' or child.tag == 'field':
                blockDict['Local Variable Names'].append(child.text)
    if type == 'text':
        for child in xmlBlock:
            if child.tag == 'title' or child.tag == 'field':
                blockDict['Strings'].append(child.text)
    subBlocks = []
    for child in xmlBlock:
        for grandchild in child:
            if grandchild.tag == 'block':
                subBlocks += findBlockInfo(grandchild)
    return [blockDict] + subBlocks

def cleanup(dirName, fileType):
    for user in os.listdir(dirName):
        user = os.path.join(dirName, user)
        if os.path.isdir(user):
          for project in os.listdir(user):
              projectPath = os.path.join(user, project)
              if projectPath.endswith(fileType):
                  os.remove(projectPath)

#cleanup('/Users/Maja/Documents/AI/ai2_users_random', '.zip')
# projectToJSONFile('/Users/Maja/Documents/AI/ai2_users_random/000044/5893134367064064.zip')
# allProjectsToJSONFiles('/Users/Maja/Documents/AI/Tutorials', 100008)
