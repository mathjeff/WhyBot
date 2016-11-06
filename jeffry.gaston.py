import subprocess
import traceback
import sys

#############################################################################################################################################################################################
#miscellaneous utils
class ShellScript(object):
  def __init__(self, commandText):
    self.commandText = commandText
    self.returnCode = None
    self.output = None

  def process(self):
    self.output = subprocess.check_output([self.commandText], stdin=None, stderr=subprocess.PIPE, shell=True)
    self.returnCode = 0

#logs to the screen
class PrintLogger(object):
  def __init__(self):
    return

  def message(self, item=""):
    print(str(item))

  def fail(self, message, justification=None):
    self.message()
    self.message("Error summary:")
    self.message(message)
    if justification is not None:
      self.message()
      self.message("Error explanation:")
      explanation = justification.explainRecursive(3)
      self.message(explanation)
    self.message()
    self.message("Error stacktrace:")
    traceback.print_stack()
    sys.exit(1)

class StringUtils(object):
  def __init__(self):
    return

  def toGetterText(self, owner, getterName):
    return self.toVariableText(str(owner)) + "." + str(getterName)

  def toVariableText(self, objectName):
    if " " in objectName:
      objectName = "(" + objectName + ")"
    return objectName

stringUtils = StringUtils()



#############################################################################################################################################################################################
#for determining where in this file (jeffry.gaston.py) we are

programLineStart = None

class ExternalStackInfo(object):
  def __init__(self):
    self.ignoredLineNumbers = []

  def setup(self):
    #make a note of the current stack to enable ignoring any lines currently active (which just participate in this custom interpreter and aren't part of the program being defined)
    lineNumbers = self.extract_lineNumbers()
    self.ignoredLineNumbers = lineNumbers
    
  def getCurrentLineNumber(self):
    ignoredLineNumber = None
    #Return the number of the line of source code in this file that defines the line currently being added to the Program
    #Only relevant if statements are being added to the Program
    for entry in self.extractStack():
      candidate = self.extract_lineNumber(entry)
      if candidate not in self.ignoredLineNumbers:
        #logger.message("Got line number of " + str(entry) + " and ignored " + str(ignoredLineNumber))
        return candidate
      else:
        ignoredLineNumber = candidate
    raise Exception("Failed to identify line number")

  def extractStack(self):
    return traceback.extract_stack()

  def extract_lineNumbers(self):
    stack = self.extractStack()
    lineNumbers = [self.extract_lineNumber(line) for line in stack]
    return lineNumbers

  def extract_lineNumber(self, entry):
    return entry[1]

externalStackInfo = ExternalStackInfo()

#############################################################################################################################################################################################
#program statements


#a program
class Program(object):
  def __init__(self):
    externalStackInfo.setup()
    self.statements = []
    self.nativeClasses = [
      NativeClassDefinition("List", (lambda: ListWrapper()), [
        NativeMethodDefinition("append", ["item"]),
        NativeMethodDefinition("getItems", []),
        NativeMethodDefinition("toString", []),
      ]),
      NativeClassDefinition("Dict", (lambda: DictionaryWrapper()), [
        NativeMethodDefinition("get", ["key"]),
      ])
    ]
    
    
  def put(self, statements):
    self.statements = self.statements + statements
    
  def run(self):
    execution = Execution(self)
    return execution.run()

class Scope(object):
  def __init__(self, execution):
    self.parent = None
    self.data = {} #Map<String, JustifiedValue>
    self.description = "Unknown scope"
    self.execution = execution

  def declareInfo(self, key, info):
    if not isinstance(info, JustifiedValue):
      raise Exception("Invalid value stored for variable " + str(key) + "; required JustifiedValue, got " + str(info))
    if key in self.data:
      raise Exception("Variable '" + key + "' already defined")
    self.data[key] = info

  def findScope(self, key):
    scope = self.tryFindScope(key)
    if scope is None:
      raise Exception("Undefined variable: '" + key + "' in " + str(self))
    return scope

  def tryFindScope(self, key):
    if key in self.data:
      return self
    if self.parent is not None:
      return self.parent.tryFindScope(key)
    return None

  def setInfo(self, key, info):
    self.findScope(key).data[key] = info

  def getInfo(self, key):
    return self.findScope(key).data[key]

  def tryGetInfo(self, key):
    scope = self.tryFindScope(key)
    if scope is None:
      return None
    return scope.data[key]

  def getValue(self, key):
    return self.getInfo(key).value

  def getJustification(self, key):
    return self.getInfo(key).justification

  def newChild(self, description=None):
    child = Object(self.execution)
    if description is None:
      description = "child scope of " + str(self.description)
    child.description = description
    child.parent = self
    return child

  def declareFunction(self, functionDefinition, justification):
    self.declareInfo(functionDefinition.functionName, JustifiedValue(functionDefinition, justification))

  def getFunction(self, functionName, callJustification):
    functionInfo = self.tryGetInfo(functionName)
    if functionInfo is None:
      logger.fail("Function '" + functionName + "' not defined in " + str(self), callJustification)
    f = functionInfo.value
    return f

  def callFunctionName(self, functionName, justifiedValues, callJustification):
    f = self.getFunction(functionName, callJustification)
    return self.callFunction(f, justifiedValues, callJustification)

  def callFunction(self, f, justifiedValues, callJustification):
    numArgumentsProvided = len(justifiedValues)
    numArgumentsRequired = len(f.argumentNames)
    if numArgumentsProvided != numArgumentsRequired:
      valueJustifications = [info.justification for info in justifiedValues]
      errorJustification = AndJustification("Gave " + str(numArgumentsProvided) + " arguments : " + str(justifiedValues) + "; required " + str(numArgumentsRequired) + " arguments: " + str(f.argumentNames), [callJustification] + valueJustifications)
      logger.fail("Invalid number of arguments to function " + str(f), errorJustification)
    child = self.execution.newScope()
    child.description = "function " + f.functionName
    #rename a bunch of variables
    for i in range(len(justifiedValues)):
      info = justifiedValues[i]
      argumentName = f.argumentNames[i]
      child.declareInfo(argumentName, info)
    result = None
    #run all the statements in the function
    for statement in f.statements:
      statement.process(callJustification)
    self.execution.removeScope()
    result = child.tryGetInfo("return") #not sure yet whether using a variable named 'return' is a hack or a feature but it's weird
    if result is not None:
      return result
    else:
      scope = child.tryFindScope("return")
      if scope is None:
        return JustifiedValue(result, TextJustification(str(f.functionName) + " did not reach any return statement"))
      else:
        return JustifiedValue(result, TextJustification(str(f.functionName) + " explicitly returned None"))



  def makeEmptyFields(self, classDefinition, newObject):
    #decide where to search for the parent class
    implScope = classDefinition.implementedInScope
    #search for the parent class
    parentClassName = classDefinition.parentClassName
    if parentClassName is not None:
      parentClass = self.getInfo(parentClassName).value
      #recurse into parent class
      self.makeEmptyFields(parentClass, newObject)
    #create eempty fields for the current class
    for fieldName in classDefinition.fieldTypes.keys(): #unfortunately the data types aren't validated yet, but they come in handy for readibility for now
      newObject.declareInfo(fieldName, JustifiedValue(None, TextJustification("The default value for a member variable is None")))
    
    
  def newObject(self, className, justifiedArguments, justification):
    classInfo = self.tryGetInfo(className)
    if classInfo is None:
      logger.fail("Class " + str(className) + " is not defined", justification)
    classDefinition = classInfo.value

    #objectDescription = "instance of " + className
    parentClassName = classDefinition.parentClassName
    newObject = self.newChild()
    #newObject.description = objectDescription
    newObject.description = className + "@" + str(newObject.objectId)


    #put empty values onto the object
    self.makeEmptyFields(classDefinition, newObject)
    implScope = classDefinition.implementedInScope
    #for itemName in implScope.data.keys():
    #  item = implScope.data[itemName]
    #  newObject.declareInfo(itemName, JustifiedValue(item.value, TextJustification("This value is defined in the class definition")))
    newObject.declareInfo("__class__", JustifiedValue(classDefinition, TextJustification("This is the class of the object")))
    #copy all the methods onto the object
    initInfo = classDefinition.implementedInScope.tryGetInfo("__init__")
    if initInfo is not None:
      #after having used the scope of the class to find the function, now use the execution scope to actually call that function
      executionScope = self
      executionScope.callFunction(initInfo.value, [JustifiedValue(newObject, TextJustification("my program specified to create an empty " + str(className)))] + justifiedArguments, justification)      
    return JustifiedValue(newObject, justification) #TODO should this justification include mention of the fact that the code said to construct the class this way?


  def __str__(self):
    return self.description

  def __repr__(self):
    return str(self)

nextObjectId = 0
#an object
class Object(Scope):
  def __init__(self, execution):
    super(Object, self).__init__(execution)
    global nextObjectId
    nextObjectId += 1
    self.objectId = nextObjectId

  def __str__(self):
    return self.description

  def toString(self, callJustification):
    return JustifiedValue(str(self), UnknownJustification())

  def callMethodName(self, methodName, justifiedValues, callJustification):
    classDefinition = self.getInfo("__class__").value
    classDefinitionImplScope = classDefinition.implementedInScope
    return classDefinitionImplScope.callFunctionName(methodName, [JustifiedValue(self, UnknownJustification())] + justifiedValues, callJustification)

#stores runtime information relating to running a program
class Execution(object):
  def __init__(self, program):
    self.program = program
    self.rootScope = Scope(self)
    self.rootScope.description = "global scope"
    self.scopes = [self.rootScope]
    self.statements = [statement for statement in program.statements]
    self.declareNativeClasses(program.nativeClasses)

  def run(self):
    return self.runStatements(self.statements)

  def runStatements(self, statements):
    result = None
    for statement in statements:
      self.ownStatement(statement)
    for statement in statements:
      justification = TextJustification(str(statement) + " is in my program")
      result = statement.process(justification)
    return result

  def ownStatement(self, statement):
    statement.beOwned(self)
    for child in statement.getChildren():
      if not hasattr(child, "beOwned"):
        raise Exception("Invalid child statement " + str(child) + " (invalid class) assigned to parent statement " + str(statement))
      self.ownStatement(child)

  def getScope(self):
    return self.scopes[-1]

  def newScope(self):
    scope = self.rootScope.newChild("scope at depth " + str(len(self.scopes)))
    self.addScope(scope)
    return self.getScope()

  def addScope(self, newScope):
    self.scopes.append(newScope)

  def removeScope(self):
    self.scopes = self.scopes[:-1]

  def declareNativeClasses(self, nativeClassDefinitions):
    for nativeClassDefinition in nativeClassDefinitions:
      self.declareNativeClass(nativeClassDefinition)

  def declareNativeClass(self, nativeClassDefinition):
    externalStackInfo.setup()
    foundInScope = self.getScope()
    managedClassName = nativeClassDefinition.managedClassName
    implementedInScope = self.rootScope.newChild(managedClassName)
    nativeClassDefinition.implementedInScope = implementedInScope
    foundInScope.declareInfo(managedClassName, JustifiedValue(nativeClassDefinition, TextJustification(str(managedClassName) + " is a built-in class")))
    for methodDefinition in nativeClassDefinition.methodDefinitions:
      nativeStatement = NativeSelfCall(methodDefinition.methodName, [Get(argumentName) for argumentName in methodDefinition.argumentNames])
      implementedInScope.declareFunction(
        FunctionDefinition(
          methodDefinition.methodName,
          ["self"] + methodDefinition.argumentNames,
          [nativeStatement]
        ),
        TextJustification(str(methodDefinition.methodName) + " is a built-in method")
      )
      self.ownStatement(nativeStatement)

    nativeStatement = NativeConstructor()
    implementedInScope.declareFunction(FunctionDefinition("__init__", ["self"], [nativeStatement]), TextJustification(str(methodDefinition.methodName) + " is a built-in method"))
    self.ownStatement(nativeStatement)


  def declareClass(self, classDefinition, justification):
    #look up the scope in which the parent class is implemented
    parentClassName = classDefinition.parentClassName
    if parentClassName is not None:
      parentClass = self.getScope().getInfo(parentClassName).value
      parentImplementationScope = parentClass.implementedInScope
    else:
      parentClass = None
      parentImplementationScope = self.rootScope
    
    implementedInScope = parentImplementationScope.newChild(classDefinition.className)
    classDefinition.implementedInScope = implementedInScope

    #get the scope in which the class can be found
    foundInScope = self.rootScope
    foundInScope.declareInfo(classDefinition.className, JustifiedValue(classDefinition, justification))

    #make any method definitions
    self.addScope(implementedInScope)
    self.runStatements(classDefinition.methodDefiners)
    self.removeScope()

#classes relating to programming
class LogicStatement(object):
  def __init__(self):
    self.execution = None
    self.children = []
    self.definitionScope = None
    self.lineNumber = externalStackInfo.getCurrentLineNumber()
    #logger.message("initialized " + repr(self))

  def beOwned(self, execution):
    self.execution = execution
    self.definitionScope = execution.getScope()

  def getChildren(self):
    return self.children

  def process(self, justification):
    raise Exception("Called abstract method 'process' of LogicStatement " + str(self))
  

#a logical 'if''
class If(LogicStatement):
  def __init__(self, condition):
    super(If, self).__init__()
    self.condition = condition
    self.trueEffects = []
    self.falseEffects = []
    self.updateChild(condition)

  def then(self, trueEffects):
    self.trueEffects = trueEffects
    self.updateChildren(trueEffects)
    return self

  def otherwise(self, falseEffects):
    self.falseEffects = falseEffects
    self.updateChildren(falseEffects)
    return self

  def updateChildren(self, children):
    for child in children:
      self.updateChild(child)

  def updateChild(self, child):
    self.children.append(child)

  def process(self, callJustification):
    result = self.condition.process(callJustification)
    description = str(self) + " was evaluated as " + str(result.value)
    childJustification = FullJustification(str(self), result.value, self.lineNumber, callJustification, [result.justification])
    if result.value == True:
      for trueEffect in self.trueEffects:
        trueEffect.process(childJustification)
    else:
      for falseEffect in self.falseEffects:
        falseEffect.process(childJustification)

  def __str__(self):
    return str(self.condition)

#a 'foreach'
class ForEach(LogicStatement):
  def __init__(self, variableName, valuesProvider, statements):
    super(ForEach, self).__init__()
    self.variableName = variableName
    self.valuesProvider = valuesProvider
    self.children.append(valuesProvider)
    self.children += statements
    self.statements = statements

  def process(self, callJustification):
    loopScope = self.execution.getScope().newChild("for loop of " + str(self.variableName))
    self.execution.addScope(loopScope)
    valueInfos = self.valuesProvider.process(callJustification)
    valuesJustification = valueInfos.justification
    loopScope.declareInfo(self.variableName, JustifiedValue(None, TextJustification("Initialized by ForEach loop")))
    values = valueInfos.value
    #print("looping over " + str(values))
    #print(valueInfos.justification.explainRecursive())
    for valueInfo in values:
      value = valueInfo.value
      justification = FullJustification(str(self.variableName), value, self.lineNumber, callJustification, [valuesJustification, valueInfo.justification])

      loopScope.setInfo(self.variableName, JustifiedValue(value, justification))

      iterationScope = self.execution.getScope().newChild("iteration where " + str(self.variableName) + " = " + str(value))
      self.execution.addScope(iterationScope)

      for statement in self.statements:
        statement.process(justification)

      self.execution.removeScope()

    self.execution.removeScope()

  def __str__(self):
    return "for " + str(self.variableName) + " in " + str(self.valuesProvider)


#a Set could be something like 'x = 5'
class Set(LogicStatement):
  def __init__(self, propertyName, valueProvider):
    super(Set, self).__init__()
    self.propertyName = propertyName
    self.valueProvider = valueProvider

  def process(self, callJustification):
    info = self.valueProvider.process(callJustification)
    justification = FullJustification(self.propertyName, info.value, self.lineNumber, callJustification, [info.justification])
    self.execution.getScope().setInfo(self.propertyName, JustifiedValue(info.value, justification))

  def getChildren(self):
    return [self.valueProvider]

  def __str__(self):
    return str(self.propertyName) + "=" + str(self.valueProvider)

#defines a variable
class Var(Set):
  def __init__(self, propertyName, valueProvider):
    super(Var, self).__init__(propertyName, valueProvider)

  def process(self, callJustification):
    try:
      self.execution.getScope().declareInfo(self.propertyName, JustifiedValue(None, TextJustification("the default variable value is None")))
      super(Var, self).process(callJustification)
    except Exception as e:
      logger.fail(traceback.format_exc(e), FullJustification("error", e, self.lineNumber, callJustification, []))

class Return(Var):
  def __init__(self, valueProvider):
    super(Return, self).__init__("return", valueProvider) #a hack for now

class FunctionDefinition(object):
  def __init__(self, functionName, argumentNames, statements):
    self.functionName = functionName
    self.argumentNames = argumentNames
    self.statements = statements


  def __str__(self):
    return self.functionName

#a function definition
class Func(LogicStatement):
  def __init__(self, functionName, argumentNames, statements):
    super(Func, self).__init__()
    self.functionName = functionName
    if not isinstance(argumentNames, list):
      raise Exception("Invalid argument " + str(argumentNames) + "; must be a list")
    self.argumentNames = argumentNames
    self.statements = statements
    self.children += statements

  def process(self, justification):
    self.execution.getScope().declareFunction(FunctionDefinition(self.functionName, self.argumentNames, self.statements), justification)

  def __str__(self):
    return "def " + str(self.functionName)

#a member function definition
#class MFunc(Func):
#  def __init__(self, functionName, argumentNames=[]):
#    super(MFunc, self).__init__(functionName, ["self"] + argumentNames)

#invokes a function
class Call(LogicStatement):
  def __init__(self, functionName, valueProviders=[]):
    super(Call, self).__init__()
    self.functionName = functionName
    self.valueProviders = valueProviders
    self.children += valueProviders

  def process(self, callJustification):
    infos = [provider.process(callJustification) for provider in self.valueProviders]
    justifications = [info.justification for info in infos]
    if self.execution is None:
      raise Exception("execution is None for " + str(self))
    text = "Call " + str(self.functionName) + "(" + ", ".join([str(info.value) for info in infos]) + ")"
    return self.execution.getScope().callFunctionName(self.functionName, infos, AndJustification(text, [callJustification]))

  def __str__(self):
    return "call " + str(self.functionName) + "(" + ", ".join([str(provider) for provider in self.valueProviders]) + ")"


#############################################################################################################################################################################################
#things relating to justifications

justificationId = 0
justificationsById = []

#class telling why something happened
class Justification(object):
  def __init__(self):
    global justificationId
    self.supporters = []
    self.justificationId = justificationId
    justificationId += 1
    justificationsById.append(self)
    self.interesting = True

  def addSupporter(self, supporter):
    if not isinstance(supporter, Justification):
      logger.fail("Invalid justification " + str(supporter) + " (not a subclass of Justification) given as support for " + str(self))
    self.supporters.append(supporter)

  def getSupporters(self):
    return self.supporters

  def describe(self):
    raise Exception("Invoked abstract method 'describe' of " + str(self))

  def explain(self):
    description = self.describe()
    reasons = [supporter.describe() for supporter in self.supporters]
    if len(reasons) > 0:
      description += " because " + ", and ".join(reasons)
    return description    

  def explainRecursive(self, maxDepth=-1):
    description = self.describeWithId()
    newlineDash = "\n|-"
    newlineIndent = "\n| "
    if maxDepth == 0:
      if len(self.supporters) != 0:
        description += " because"
        description += newlineDash + " (more)"
    else:
      interestingChildren = self.getInterestingChildren()
      #if len(self.supporters) == 1:
      #  #description = "(skipping " + description + ")\n" anything with only one justification is considered too simple to be worth explaining
      #  description = self.supporters[0].explainRecursive(maxDepth)
      #  return description
      description += " because"
      for reasonIndex in range(len(interestingChildren)):
        reason = interestingChildren[reasonIndex]
        if reasonIndex > 0:
          description += newlineIndent
        lines = reason.explainRecursive(maxDepth - 1).split("\n")
        for lineIndex in range(len(lines)):
          line = lines[lineIndex]
          if lineIndex == 0:
            description += newlineDash + line
          else:
            description += newlineIndent + line
    return description

  def getInterestingChildren(self):
    results = []
    for child in self.supporters:
      if child.interesting:
        results.append(child)
      else:
        for descendent in child.getInterestingChildren():
          if descendent not in results:
            results.append(descendent)
    return results

  def describeWithId(self):
    return "- (#" + str(self.justificationId) + ") " + self.describe()

  def explainOneLevel(self):
    description = self.describeWithId()
    if len(self.supporters) > 0:
      description += " because"
    indent = "| "
    for reason in self.supporters:
      for line in reason.describeWithId().split("\n"):
        description += "\n" + indent + line
    return description

#justification of something that's only represented by text'
class TextJustification(Justification):
  def __init__(self, message):
    super(TextJustification, self).__init__()
    self.message = message

  def describe(self):
    return self.message

#class for when we don't know the justification'
class UnknownJustification(TextJustification):
  def __init__(self):
    super(UnknownJustification, self).__init__("""Idk.""")

#justification of something caused by other things	
class AndJustification(Justification):
  def __init__(self, description, justifications):
    super(AndJustification, self).__init__()
    self.description = description
    for justification in justifications:
      self.addSupporter(justification)
    if "__main__" in description:
      logger.fail("Invalid description passed to AndJustification: " + description, self)

  def describe(self):
    return str(self.description)

  
#says that two things are equal
class EqualJustification(Justification):
  def __init__(self, description, value, valueJustification):
    super(EqualJustification, self).__init__()
    self.itemDescription = description
    self.itemValue = value
    self.valueJustification = valueJustification
    self.addSupporter(self.valueJustification)

  def describe(self):
    return self.itemDescription + ' equals "' + str(self.itemValue) + '"'

class FullJustification(Justification):
  def __init__(self, variableName, value, logicLocation, callJustification, valueJustifications):
    super(FullJustification, self).__init__()
    self.variableName = variableName
    self.value = value
    self.callJustification = callJustification
    self.logicLocation = logicLocation
    self.valueJustifications = valueJustifications
    if not isinstance(valueJustifications, list):
      logger.fail("Invalid (non-list) value provided for argument 'justifications' to FullJustification.__init__", callJustification)
    for supporter in [callJustification] + valueJustifications:
      self.addSupporter(supporter)
    if self.logicLocation is None:
      logger.fail("Empy logicLocation for FullJustification", callJustification)
    self.interesting = True

  def describe(self):
    message = ""
    #if self.logicLocation is not None:
    message += "[line " + str(self.logicLocation) + "]: "
    message += stringUtils.toVariableText(self.variableName) + " = " + str(self.value)
    return message

  def explainRecursive(self, maxDepth=-1):
    description = self.describeWithId()
    newlineDash = "\n|-"
    newlineIndent = "\n| "
    if maxDepth == 0:
      if len(self.supporters) != 0:
        description += " because"
        description += newlineDash + " (more)"
    else:
      interestingChildren = self.getInterestingChildren()
      #if len(self.supporters) == 1:
      #  #description = "(skipping " + description + ")\n" anything with only one justification is considered too simple to be worth explaining
      #  description = self.supporters[0].explainRecursive(maxDepth)
      #  return description
      description += " because"
      for reasonIndex in range(len(interestingChildren)):
        if reasonIndex > 0:
          description += newlineIndent
        reason = interestingChildren[reasonIndex]
        description += newlineDash
        if reason == self.callJustification:
          description += "Called because"
        else:
          description += "True because"      
        lines = reason.explainRecursive(maxDepth - 1).split("\n")
        for lineIndex in range(len(lines)):
          line = lines[lineIndex]
          description += newlineIndent + line
    return description



#contains a value and a justification
class JustifiedValue(object):
  def __init__(self, value, justification):
    if value is not None and isinstance(value, JustifiedValue):
      logger.fail("JustifiedValue (" + str(value) + ") was given as the value of a JustifiedValue, which is unnecessary redundancy")
    self.value = value
    if not isinstance(justification, Justification):
      logger.fail("Invalid justification " + str(justification) + " (not a subclass of Justification) given for " + str(value))
    self.justification = justification

  def __str__(self):
    return str(self.value)

  def __repr__(self):
    return str(self)

#############################################################################################################################################################################################
#TThings relating to value providers

#abstract class that returns a value
class ValueProvider(object):
  def __init__(self):
    self.execution = None
    self.lineNumber = externalStackInfo.getCurrentLineNumber()
    
  def beOwned(self, execution):
    self.execution = execution
    self.definitionScope = execution.getScope()

  def process(self, justification):
    raise Exception("Invoked abstract method 'process' of ValueProvider")

  def getChildren(self):
    return []

#returns a constant
class Const(ValueProvider):
  def __init__(self, value):
    super(Const, self).__init__()
    self.value = value

  def process(self, justification):
    return JustifiedValue(self.value, TextJustification("'" + str(self.value) + "' is in my program"))

  def __str__(self):
    return str(self.value)

#gets a variable from the current scope
class Get(ValueProvider):
  def __init__(self, propertyName):
    super(Get, self).__init__()
    self.propertyName = propertyName

  def process(self, callJustification):
    if self.execution is None:
      logger.fail("execution is None for " + str(self), callJustification)
    scope = self.execution.getScope()
    try:
      info = scope.getInfo(self.propertyName)
    except Exception as e:
      logger.fail(str(self) + " failed", AndJustification(str(e), [callJustification]))
    if not isinstance(info, JustifiedValue):
      raise Exception("Invalid value stored for variable " + str(self.propertyName) + "; required JustifiedValue, got " + str(info))
    storeJustification = info.justification

    justification = FullJustification(str(self.propertyName), info.value, self.lineNumber, callJustification, [storeJustification])
    return JustifiedValue(info.value, justification)
    #return JustifiedValue(info.value, AndJustification(str(self.propertyName) + " = " + str(info.value) + " (in " + str(scope) + ")", [callJustification, storeJustification]))

  def __str__(self):
    return "get " + str(self.propertyName)

#convert to int
class Int(ValueProvider):
  def __init__(self, inputProvider):
    super(Int, self).__init__()
    self.inputProvider = inputProvider

  def process(self, justification):
    inputInfo = self.inputProvider.process(justification)
    try:
      outputValue = int(inputInfo.value)
    except ValueError as e:
      outputValue = None
    return JustifiedValue(outputValue, inputInfo.justification)

  def getChildren(self):
    return [self.inputProvider]

  def __str__(self):
    return "int(" + str(self.inputProvider) + ")"


#gets a justification
class JustificationGetter(ValueProvider):
  def __init__(self, idProvider):
    super(JustificationGetter, self).__init__()
    self.idProvider = idProvider

  def process(self, callJustification):
    idInfo  = self.idProvider.process(callJustification)
    value = idInfo.value
    if value is not None:
      justification = justificationsById[value]
      return JustifiedValue(justification, justification)
    else:
      return JustifiedValue(None, callJustification)

  def getChildren(self):
    return [self.idProvider]

  def __str__(self):
    return "lookup justification " + str(self.idProvider)

#
class Ask(ValueProvider):
  def __init__(self, promptProvider=None):
    self.promptProvider = promptProvider

  def process(self, justification):
    prompt = self.promptProvider.process(justification).value
    try:
      result = raw_input(prompt)
    except EOFError as e:
      sys.exit(0)
    message = "You entered '" + str(result) + "'"
    if prompt is not None:
      message += " when asked '" + str(prompt) + "'"
    return JustifiedValue(result, TextJustification(message))

  def getChildren(self):
    result = []
    if self.promptProvider is not None:
      result.append(self.promptProvider)
    return result

#tells whether two things are equal
class Eq(ValueProvider):
  def __init__(self, provider1, provider2):
    super(Eq, self).__init__()
    self.provider1 = provider1
    self.provider2 = provider2
      

  def process(self, callJustification):
    info1 = self.provider1.process(callJustification)
    info2 = self.provider2.process(callJustification)
    matches = (info1.value == info2.value)
    description = str(self.provider1)
    if matches:
      description += "="
    else:
      description += "!="
    description += str(self.provider2)
    #return JustifiedValue(matches, AndJustification(description, [EqualJustification('value 1', info1.value, info1.justification), EqualJustification('value 2', info2.value, info2.justification)]))
    justification1 = FullJustification(str(self.provider1), info1.value, self.lineNumber, callJustification, [info1.justification])
    justification2 = FullJustification(str(self.provider2), info1.value, self.lineNumber, callJustification, [info2.justification])
    return JustifiedValue(matches, AndJustification(description, [justification1, justification2]))

  def getChildren(self):
    return [self.provider1, self.provider2]

  def __str__(self):
    return str(self.provider1) + "==" + str(self.provider2)


#############################################################################################################################################################################################
#gets a variable from the current scope
class Plus(ValueProvider):
  def __init__(self, valueProviders):
    super(Plus, self).__init__()
    self.valueProviders = valueProviders

  def process(self, callJustification):
    infos = [provider.process(callJustification) for provider in self.valueProviders]
    sum = infos[0].value
    for otherInfo in infos[1:]:
      sum += otherInfo.value
    justifications = [info.justification for info in infos]
    #return JustifiedValue(sum, AndJustification(self.getVariableName() + " equals " + str(sum) + " (in " + str(self.definitionScope) + ")", justifications))
    justification = FullJustification(self.getVariableName(), sum, self.lineNumber, callJustification, justifications)
    return JustifiedValue(sum, justification)

  def getChildren(self):
    return self.valueProviders

  def getVariableName(self):
    return "sum"

  def __str__(self):
    return "+".join([str(provider) for provider in self.valueProviders])

#string concatenation
class Concat(Plus):
  def __init__(self, valueProviders):
    super(Concat, self).__init__(valueProviders)

  def getVariableName(self):
    return "concatenation"

#some math

#############################################################################################################################################################################################
#Some I/O
class Print(LogicStatement):
  def __init__(self, messageProvider):
    super(Print, self).__init__()
    self.messageProvider = messageProvider
    if self.messageProvider is None:
      self.messageProvider = Const("")
    self.children.append(self.messageProvider)

  def process(self, justification):
    #It's helpful to know that this program uses two systems of converting to a string
    
    #The __str__ method is built into the custom interpreter and is what the custom interpreter uses, because it needs a method without side-effects
    #The interpreter records justifications for essentially everything, and needs to have a way to describe its justifications
    #These descriptions might be somewhat simple, like class names, method names, and argument names

    #the toString method is to be used by classes that are implemented inside the interpreter
    #the toString method can be more complicated and contain custom logic because it doesn't need to be invoked as a side-effect of invoking most other lines
    #it only gets invoked when other lines of code directly invoke it

    info = self.messageProvider.process(justification)
    logger.message(info.value)
    return info

  def __str__(self):
    return "Print(" + str(self.messageProvider) + ")"

class FullExplain(Print):
  def __init__(self, messageProvider):
    super(FullExplain, self).__init__(messageProvider)

  def process(self, justification):
    info = self.messageProvider.process(justification)
    logger.message(info.justification.explainRecursive())
    return info

  def __str__(self):
    return "FullExplain(" + str(self.messageProvider) + ")"


class ShortExplain(Print):
  def __init__(self, messageProvider, depthProvider):
    super(ShortExplain, self).__init__(messageProvider)
    self.depthProvider = depthProvider

  def process(self, justification):
    info = self.messageProvider.process(justification)
    depthInfo = self.depthProvider.process(justification)
    logger.message(info.justification.explainRecursive(depthInfo.value))
    return info

  def __str__(self):
    return "ShortExplain(" + str(self.messageProvider) + ", " + str(self.depthProvider) + ")"

#############################################################################################################################################################################################
#Things pertaining to class definitions
    
#the definition of a class
class ClassDefinition(object):
  def __init__(self, className, parentClassName, fieldTypes, methodDefiners=[]):
    self.className = className
    self.parentClassName = parentClassName
    if not isinstance(fieldTypes, dict):
      raise Exception("Invalid data type for fieldTypes of class " + str(className) + ": expected dict, got " + str(fieldTypes))
    self.fieldTypes = fieldTypes
    self.implementedInScope = None
    self.methodDefiners = methodDefiners

  def __str__(self):
    return "classdef:" + str(self.className)

#declares a class
class Class(LogicStatement):
  def __init__(self, className): #, parentClassName = None, fieldTypes = {}, methodDefiners = []):
    super(Class, self).__init__()
    self.className = className
    self.parentClassName = None
    self.fieldTypes = {}
    self.methodDefiners = []
    
  def inherit(self, parentClassName):
    self.parentClassName = parentClassName
    return self

  def vars(self, fieldTypes):
    self.fieldTypes = fieldTypes
    return self

  def func(self, methodName, argumentNames, statements):
    f = Func(methodName, ["self"] + argumentNames, statements)
    self.methodDefiners.append(f)
    self.children.append(f)
    return self #to enable the caller to call 'when' and put a function body

  def init(self, argumentNames, statements):
    #If any init arguments match declared variable names, then copy them automatically. Isn't it cool inventing a new language and being able to add this kind of thing?
    valueCopierStatements = []
    for argumentName in argumentNames:
      if argumentName in self.fieldTypes:
        valueCopierStatements.append(SelfSet(argumentName, Get(argumentName)))
    return self.func("__init__", argumentNames, valueCopierStatements + statements)

  def process(self, justification):
    classDefinition = ClassDefinition(self.className, self.parentClassName, self.fieldTypes, self.methodDefiners)
    self.execution.declareClass(classDefinition, justification)
    
  def __str__(self):
    return "declare class " + str(self.className)


#makes a new object
class New(ValueProvider):
  def __init__(self, className, argumentProviders=[]):
    super(ValueProvider, self).__init__()
    self.className = className
    self.argumentProviders = argumentProviders

  def process(self, justification):
    argumentInfos = [item.process(justification) for item in self.argumentProviders]
    justifications = [justification] + [item.justification for item in argumentInfos]
    numNonSelfParameters = len(justifications) - 1

    text = "new " + str(self.className) + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")"
    result = self.execution.getScope().newObject(self.className, argumentInfos, AndJustification(text, justifications))
    return result

  def getChildren(self):
    return self.argumentProviders

  def __str__(self):
    return "new " + str(self.className) + "(" + ", ".join([str(item) for item in self.argumentProviders]) + ")"
    
#sets a property of an object - nearly the same as Set
class DotSet(LogicStatement):
  def __init__(self, ownerProvider, propertyName, valueProvider):
    super(DotSet, self).__init__()
    self.ownerProvider = ownerProvider
    self.propertyName = propertyName
    self.valueProvider = valueProvider
    self.children += [ownerProvider, valueProvider]

  def process(self, callJustification):
    ownerInfo = self.ownerProvider.process(callJustification)
    owner = ownerInfo.value
    valueInfo = self.valueProvider.process(callJustification)
    value = valueInfo.value
    #owner.setInfo(self.propertyName, JustifiedValue(value, AndJustification(stringUtils.toGetterText(owner, self.propertyName) + "=" + str(value), [justification, valueInfo.justification])))
    justification = FullJustification(stringUtils.toGetterText(owner, self.propertyName), value, self.lineNumber, callJustification, [valueInfo.justification])
    owner.setInfo(self.propertyName, JustifiedValue(value, justification))

#sets a property of self
class SelfSet(DotSet):
  def __init__(self, propertyName, valueProvider):
    super(SelfSet, self).__init__(Get("self"), propertyName, valueProvider)

#returns a property of an object - nearly the same as Get
class DotGet(ValueProvider):
  def __init__(self, ownerProvider, propertyName):
    super(DotGet, self).__init__()
    self.ownerProvider = ownerProvider
    self.propertyName = propertyName
    self.children = [self.ownerProvider]

  def process(self, callJustification):
    ownerInfo = self.ownerProvider.process(callJustification)
    owner = ownerInfo.value
    if owner is None:
      logger.fail("object to dereference is None", ownerInfo.justification)
    valueInfo = owner.getInfo(self.propertyName)
    description = stringUtils.toGetterText(owner, self.propertyName)
    justification = FullJustification(description, valueInfo.value, self.lineNumber, callJustification, [ownerInfo.justification, valueInfo.justification])
    #return JustifiedValue(valueInfo.value, AndJustification(description, [ownerInfo.justification, valueInfo.justification]))
    return JustifiedValue(valueInfo.value, justification)

  def getChildren(self):
    return self.children

  def __str__(self):
    return str(self.ownerProvider) + "." + str(self.propertyName)

#gets a property of self
class SelfGet(DotGet):
  def __init__(self, propertyName):
    super(SelfGet, self).__init__(Get("self"), propertyName)


#returns the scope in which the current class is defined (so almost the ClassDefinition)
class DefinedInClass_Scope(ValueProvider):
  def __init__(self):
    super(DefinedInClass_Scope, self).__init__()

  def process(self, justification):
    return JustifiedValue(self.definitionScope, UnknownJustification())

  def __str__(self):
    return str(self.definitionScope)

#returns the parent of the scope in which the current class is defined (so almost the parent's ClassDefinition)
class SuperScope(DefinedInClass_Scope):
  def process(self, justification):
    return JustifiedValue(self.definitionScope.parent, TextJustification("parent scope of " + str(self.definitionScope) + " is " + str(self.definitionScope.parent)))

  def __str__(self):
    return str(self.definitionScope) + ".super"

#returns the class scope for a given object
class ClassFromObject_Scope(ValueProvider):
  def __init__(self, objectProvider):
    super(ClassFromObject_Scope, self).__init__()
    self.objectProvider = objectProvider

  def process(self, callJustification):
    objectInfo = self.objectProvider.process(callJustification)
    objectValue = objectInfo.value
    justification = AndJustification("Check class of " + str(objectValue), [callJustification, EqualJustification("method owner", objectValue, objectInfo.justification)])
    try:
      classInfo = objectValue.tryGetInfo("__class__")
    except Exception as e:
      logger.fail(str(self) + " failed", justification)
    classDefinition = classInfo.value
    classScope = classDefinition.implementedInScope
    return JustifiedValue(classScope, TextJustification("(" + str(objectValue) + ") instanceof " + str(classDefinition)))

  def getChildren(self):
    return [self.objectProvider]

  def __str__(self):
    return "main scope"

#returns the class scope inside the current object (which may be a subclass of the class doing the asking)
class SelfScope(ClassFromObject_Scope):
  def __init__(self):
    super(SelfScope, self).__init__(Get("self"))

  def __str__(self):
    return "scope of self"

#calls a particular method on a particular object
class DotCallImpl(LogicStatement):
  def __init__(self, classScope_provider, methodName, argumentProviders=[]):
    super(DotCallImpl, self).__init__()
    self.classScope_provider = classScope_provider
    self.methodName = methodName
    if not isinstance(argumentProviders, list):
      raise Exception("Arguments to " + str(methodName) + " must be be a list")
    self.argumentProviders = argumentProviders
    self.children.append(classScope_provider)
    self.children += argumentProviders

  def process(self, callJustification):
    classScope_info = self.classScope_provider.process(AndJustification("[" + str(self.lineNumber) + "]: Calling " + str(self), [callJustification]))
    classScope = classScope_info.value
    classScope_Justification = EqualJustification("self", classScope, classScope_info.justification)
    argumentInfos = [provider.process(callJustification) for provider in self.argumentProviders]
    argumentJustifications = [info.justification for info in argumentInfos[1:]]
    selfJustification = argumentInfos[0].justification
    numNonSelfParameters = len(argumentInfos) - 1
    text = "Evaluated " + str(self)
    #argumentJustification = AndJustification(text, argumentJustifications)
    #overallJustification = AndJustification(text, [callJustification, selfJustification, argumentJustification])
    #overallJustification = FullJustification(str(self), "result", self.lineNumber, callJustification, [selfJustification, argumentJustification])
    contextJustification = AndJustification("[line " + str(self.lineNumber) + "]: " + text, [callJustification, selfJustification] + argumentJustifications)
    f = classScope.getFunction(self.methodName, contextJustification)
    #result = self.execution.getScope().callFunction(f, argumentInfos, overallJustification)
    result = self.execution.getScope().callFunction(f, argumentInfos, contextJustification)
    justification = FullJustification(str(self), result.value, self.lineNumber, callJustification, [result.justification])
    return JustifiedValue(result.value, justification)

  def __str__(self):
    #return "(" + str(self.classScope_provider) + "): (" + str(self.argumentProviders[0]) + ")." + str(self.methodName) + "(" + ", ".join([str(provider) for provider in self.argumentProviders[1:]]) + ")"
    return "(" + str(self.argumentProviders[0]) + ")." + str(self.methodName) + "(" + ", ".join([str(provider) for provider in self.argumentProviders[1:]]) + ")"

#calls a particular method on the superclass
class SuperCall(DotCallImpl):
  def __init__(self, methodName, argumentProviders=[]):
    super(SuperCall, self).__init__(SuperScope(), methodName, [Get("self")] + argumentProviders)

#calls a particular method on the current object
class SelfCall(DotCallImpl):
  def __init__(self, methodName, argumentProviders=[]):
    super(SelfCall, self).__init__(SelfScope(), methodName, [Get("self")] + argumentProviders)

class DotCall(DotCallImpl):
  def __init__(self, objectProvider, methodName, argumentProviders=[]):
    super(DotCall, self).__init__(ClassFromObject_Scope(objectProvider), methodName, [objectProvider] + argumentProviders)

#for calling python methods directly
class NativeSelfCall(LogicStatement):
  def __init__(self, methodName, argumentProviders=[]):
    super(NativeSelfCall, self).__init__()
    self.managedObject_provider = Get("self")
    self.methodName = methodName
    self.argumentProviders = argumentProviders
    self.children.append(self.managedObject_provider)
    self.children += argumentProviders

  def process(self, callJustification):
    managedObject_info = self.managedObject_provider.process(callJustification)
    managedObject = managedObject_info.value
    selfJustification = managedObject_info.justification
    nativeObject = managedObject.nativeObject
    argumentInfos = [provider.process(callJustification) for provider in self.argumentProviders]
    argsText = "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")"
    #argumentsJustification = AndJustification(argsText, [info.justification for info in argumentInfos])
    argumentsJustification = FullJustification("arguments", argsText, self.lineNumber, callJustification, [info.justification for info in argumentInfos])
    allJustifications = [callJustification] + [info.justification for info in argumentInfos]
    try:
      nativeMethod = getattr(nativeObject, self.methodName)
    except Exception as e:
      logger.fail(str(self) + " failed", AndJustification(str(e), [callJustification, argumentsJustification]))
    historyJustification = AndJustification("Called (unmanaged) " + str(nativeObject) + "." + self.methodName + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")", [callJustification, selfJustification] + [argumentsJustification])
    #historyJustification.interesting = False
    args = [historyJustification] + [info for info in argumentInfos]
    count = len(args)
    if count == 0:
      result = nativeMethod()
    elif count == 1:
      result = nativeMethod(args[0])
    elif count == 2:
      result = nativeMethod(args[0], args[1])
    elif count == 3:
      result = nativeMethod(args[0], args[1], args[2])
    elif count == 4:
      result = nativeMethod(args[0], args[1], args[2], arg[3])
    elif count == 5:
      result = nativeMethod(args[0], args[1], args[2], arg[3], arg[4])
    elif count == 6:
      result = nativeMethod(args[0], args[1], args[2], arg[3], arg[4], arg[5])
    elif count == 7:
      result = nativeMethod(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6])
    elif count == 8:
      result = nativeMethod(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6], arg[7])
    elif count == 9:
      result = nativeMethod(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6], arg[7], arg[8])
    else:
      #TODO there must be a better way to do this
      logger.fail("Too many arguments", AndJustifications(str(count) + " arguments", allJustifications))
    #info = JustifiedValue(result.value, AndJustification(str(nativeObject) + "." + self.methodName + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ") = " + str(result), [result.justification]))
    justification = FullJustification("unmanaged " + str(nativeObject) + "." + self.methodName + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")", result.value, self.lineNumber, callJustification, [result.justification])
    #justification.interesting = False
    self.execution.getScope().declareInfo("return", JustifiedValue(result.value, justification))
    return result

#for constructing
class NativeConstructor(LogicStatement):
  def __init__(self):
    super(NativeConstructor, self).__init__()
    self.managedObject_provider = Get("self")
    self.children.append(self.managedObject_provider)

  def process(self, callJustification):
    managedObject_info = self.managedObject_provider.process(callJustification)
    managedObject = managedObject_info.value
    classInfo = managedObject.getInfo("__class__")
    classDefinition = classInfo.value
    constructor = classDefinition.constructor
    managedObject.nativeObject = constructor()

#the definition of a class that's implemented by a native class
class NativeClassDefinition(object):
  def __init__(self, managedClassName, constructor, methodDefinitions):
    self.managedClassName = managedClassName
    self.constructor = constructor
    self.methodDefinitions = methodDefinitions
    self.implementedInScope = None
    self.parentClassName = None
    self.fieldTypes = {}
    self.implementedInScope = None

  def __str__(self):
    return "native classdef:" + str(self.managedClassName)

#the definition of a method that's implemented by a native method'
class NativeMethodDefinition(object):
  def __init__(self, methodName, argumentNames=[]):
    self.methodName = methodName
    self.argumentNames = argumentNames
    

class ListWrapper(object):
  def __init__(self):
    super(ListWrapper, self).__init__()
    self.justifications = []
    self.impl = []

  def append(self, callJustification, item):
    if not isinstance(item, JustifiedValue):
      logger.fail("Invalid item " + str(item) + " (not a subclass of JustifiedValue) appended to " + str(self), callJustification)
    #if not hasattr(item.value, "callMethodName"):
    #  logger.fail("Invalid item " + str(item) + " (not managed object) appended to " + str(self), callJustification)
    self.impl.append(JustifiedValue(item.value, AndJustification("appended " + str(item.value) + " to " + str(self.impl), [callJustification, item.justification])))
    #self.justifications.append(JustifiedValue(item, callJustification))
    return JustifiedValue(None, callJustification)

  def getItems(self, callJustification):
    #return self
    return JustifiedValue(self.impl, AndJustification("Contents of " + str(self) + " = " + str([info.value for info in self.impl]), [callJustification] + [info.justification for info in self.impl]))
    #return JustifiedValue(self, AndJustification("List contents", [callJustification] + self.justifications))

  def toString(self, callJustification):
    tostringInfos = []
    texts = []
    allJustifications = []
    for info in self.impl:
      value = info.value
      allJustifications.append(info.justification)
      if hasattr(value, "callMethodName"):
        elementInfo = value.callMethodName("toString", [], callJustification)
        tostringInfos.append(elementInfo)
        texts.append(elementInfo.value)
        allJustifications.append(info.justification)
      else:
        #TODO should we make a StringWrapper class instead of type-checking here?
        #calling toString of a native class is too simple to be worth explaining so we just skip explaining it (and below we explain how the element was put into the list to begin with)
        texts.append(str(value))
        
    result =  "[" + ", ".join([text for text in texts]) + "]"
    justificationText  =  "Returned List.toString() = " + result
    elementsJustification = AndJustification(justificationText, [callJustification] + allJustifications)
    #elementsJustification = FullJustification("toString", result, None, callJustification, allJustifications)
    return JustifiedValue(result, elementsJustification)
    #return JustifiedValue(result, AndJustification(justificationText, [callJustification, elementsJustification]))

  def __str__(self):
    return str(self.impl)

class DictionaryWrapper(object):
  def __init__(self):
    super(DictionaryWrapper, self).__init__()
    self.items = {}

  def get(self, callJustification, key):
    if key not in self.items:
      return JustifiedValue(None, AndJustification(str(key) + " not found in " + str(self), [callJustification]))
    info = self.items.get(key)
    return JustifiedValue(info.value, AndJustification(str(key) + " retrieved from " + str(self), [callJustification, info.justification]))

  def __str__(self):
    return str(self.items)
      

#############################################################################################################################################################################################
#some exceptions
class InterpreterException(LogicStatement):
  def __init__(self, message):
    super(InterpreterException, self).__init__()
    self.message = message

  def process(self, callJustification):
    logger.fail(self.message, callJustification)

  def __str__(self):
    return "raise Exception(" + self.message + ")"

class AbstractException(InterpreterException):
  def __init__(self):
    super(AbstractException, self).__init__("called abstract method")

#############################################################################################################################################################################################
#miscellaneous
class JustifiedShell(ValueProvider):
  def __init__(self, commandText_provider):
    self.commandText_provider = commandText_provider

  def process(self, justification):
    commandInfo = self.commandText_provider.process()
    script = ShellScript(commandInfo.value)
    script.process()
    value = script.output.strip()
    return JustifiedValue(value, AndJustification([EqualJustification('script provider', self.commandText_provider, UnknownJustification()),
                                           EqualJustification('script command', commandInfo.value, commandInfo.justification), 
                                           EqualJustification('script output', value, TextJustification("That is the result that the shell gave"))]))


def getModificationExpression():
  return JustifiedShell(Const("stat --format %y jeffry.gaston.py  | grep -o 2016-10-05"))

def get_currentHash_expression():
  return JustifiedShell(Const("head -n `wc -l jeffry.gaston.py | sed 's/ .*//'` jeffry.gaston.py  | md5sum | sed 's/^/#/'"))

def get_savedHash_expression():
  return JustifiedShell(Const("tail -n 1 jeffry.gaston.py"))

def make_fileModified_expression():
  return Eq(get_savedHash_expression(), get_currentHash_expression())

logger = PrintLogger()

def equalityCheck():
  program = Program()
  storage = program.storage
  program.put([
    Set(storage, "a", Const("one")),
    Set(storage, "b", Const("two")),
    If(Eq(Get("a"), Get("b"))).then(
      Set(storage, "result", Const("equal")),
      Set(storage, "result", Const("different"))
    )
  ])
  program.run()
  result = storage.getInfo("result")
  logger.message()
  logger.message("Program result value = " + str(result.value) + " because " + str(result.justification.explainRecursive()))

def suggestion():
  program = Program()
  program.put([
    #some high-level ideas to try:
    #hardcoded prompts
      #recommend reading the logs
      #recommend googling it
      #recommend asking someone for help
      #recommend diff-filterer.py
      #recommend `diff -r`
      #recommend reading the source code
      #recommend experimenting with edits to the source code
      #recommend taking a break

    #git log filename and suggest asking the author
    #query the wiki
    #make a new wiki page
    #query jira
    #query google
    #query/update a new special-purpose database
      #possibly a baysian filter telling who to ask based on words in the query
    #try to parse the log and highlight some important text
    #grep notes
    #parse a log file and compare to the source code to describe what happened
    
    #some jokes
      #reject "As a..."


    #class Solution, which has prerequisites, an activity, and a resulting change
    #class Activity, which has an Actor, a verb, and a possibly something else, depending on which Activity it is
    #For example:
    #
    #problem: "X"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"find", object: "a knowledgeable entity")
    #  Action(actor:"you", verb:"adk", about:"the entity for help")
    #  resulting change: "X is solved"
    #
    #problem: "X does not work"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"understand", object: "the problem")
    #  Action(actor:"you", verb:"do", about:"the obvious")
    #  resulting change: "X works"
    #
    #problem: "don't understand the problem"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"read", object: "clear logs")
    #  Action(actor:"you", verb:"think", about:"the logs")
    #  resulting change: "you understand the problem"
    #
    #problem: "don't understand the problem"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"found", object: "any logs")
    #  Action(actor:"I", verb:"analyze", about:"the logs")
    #  resulting change: "you understand the problem"
    #
    #problem: "don't understand the problem"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"have", object: "a version that works")
    #  Action(actor:"you", verb:"diff", what:"the one that works with the onw that doesn't work")
    #  resulting change: "you understand the problem"
    #
    #problem: "don't understand the problem"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"can", what: "wait")
    #  Action(actor:"you", verb:"rest", until:"you feel better")
    #  resulting change: "you understand the problem"
    #
    #problem: "don't understand the problem"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"can", what: "wait")
    #  Action(actor:"you", verb:"rest", until:"the problem happens again")
    #  resulting change: "you understand the problem"
    #
    #problem: "don't have clear logs"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"jave", object: "good source code")
    #  Action(actor:"you", verb:"rerun", about:"the program")
    #  resulting change: "you have clear logs"
    #
    #problem: "don't have good source code"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"understand", object: "the source code")
    #  Action(actor:"you", verb:"improve", about:"the source code")
    #  resulting change: "you have good source code"
    #
    #problem: "don't understand the source code"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"found", object: "the source code")
    #  Action(actor:"you", verb:"read", about:"the source code")
    #  resulting change: "you understand the source code"
    #

    #problem: "cannot find a knowledgeable entity"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"have", object: "an instance messenger")
    #  Action(actor:"you", verb:"check", object:"the instant messenger's contact list")
    #  resulting change: "found a knowledgeable entity"
    #
    #problem: "cannot find a knowledgeable entity"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"have", object: "internet access")
    #  Action(actor:"you", verb:"use", object:"google.com as your knowledgeable entity")
    #  resulting change: "found a knowledgeable entity"
    #
    #problem: "cannot find a knowledgeable entity"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"have", object: "internet access")
    #  Action(actor:"you", verb:"check", object:"the company wiki")
    #  resulting change: "found a knowledgeable entity"
    #
    #problem: "cannot find a knowledgeable entity"
    #solution:
    #  prerequisite: Action(actor:"you", verb:"have", object: "source code")
    #  Action(actor:"you", verb:"execute", object:"git log ${filename}")
    #  resulting change: "found a knowledgeable entity"
    #




    #a thing that can be done
    Class("Action")
      .func("execute", [], [
        AbstractException()
      ]),

    #an Action that prints a message
    Class("TextAction")
      .vars({"message": "string"})
      .init(["message"], [
      ])
      .func("execute", [], [
        Print(SelfGet("message")),
      ])
      .func("toString", [], [
        Return(SelfGet("message"))
      ]),

    Class("Universe")
      .vars({"props":"Map<string,string>"})
      .init([], [
        SelfSet("props", New("Dict")),
      ])
      .func("getProp", ["key"], [
        Return(DotCall(SelfGet("props"), "get", [Get("key")])),
      ])
      .func("putProp", ["key", "value"], [
        DotCall(SelfGet("props"), "put", [Get("key"), Get("value")]),
      ]),

    Class("Proposition")
      .func("evaluate", ["universe"], [
        AbstractException()
      ]),

    #a Proposition without much logic - it just asks the Universe what its value is
    Class("TextProposition")
      .inherit("Proposition")
      .vars({"text": "string"})
      .init(["text"], [
      ])
      .func("evaluate", ["universe"], [
        Return(DotCall(Get("universe"), "getProp", [SelfGet("text")])),
      ])
      .func("equals", ["other"], [
        Return(Eq(SelfGet("text"), DotGet(Get("other"), "text"))),
      ])
      .func("toString", [], [
        Return(SelfGet("text"))
      ]),


    #a Predicate to be tested and a desired outcome for that predicate
    Class("Problem")
      .vars({"proposition":"Proposition", "desiredOutcome":"object"})
      .init(["proposition", "desiredOutcome"], [
      ])
      .func("isSolved", ["universe"], [
        Var("result", DotCall(SelfGet("proposition"), "evaluate")),
        If(Eq(Get("result"), Const(True))).then([
          Return(Const(True)),
        ]).otherwise([
          Return(Const(False))
        ]),
      ])
      .func("equals", ["problem"], [
        Var("sameCheck", DotCall(SelfGet("proposition"), "equals", [DotGet(Get("problem"), "proposition")])),
        If(Eq(Get("sameCheck"), Const(True))).then([
          Var("sameOutcome", Eq(SelfGet("desiredOutcome"), DotGet(Get("problem"), "desiredOutcome"))),
          Return(Get("sameOutcome")), #we could do fancy more-accurate things like checking for inverted checks with inverted outcomes, but we're not doing that for now
        ]).otherwise([
          Return(Const(False)),
        ])
      ])
      .func("toString", [], [
        Return(DotCall(SelfGet("proposition"), "toString")),
      ]),

    #a problem to be solved, a way to solve it, and a prerequisite to being able to solve it
    Class("Solution")
      .vars({"problem":"Problem", "prerequisite":"Proposition", "fix":"Action"})
      .init(["problem", "prerequisite", "fix"], [      
      ])
      .func("toString", [], [
        Return(Concat([
          Const('If "'),
          DotCall(SelfGet("prerequisite"), "toString"),
          Const('" and "'),
          DotCall(SelfGet("fix"), "toString"),
          Const('" then "'),
          DotCall(SelfGet("problem"), "toString"),
          Const('" should be all set.'),
        ]))
      ]),

    #searches a list of solutions for a relevant solution
    Class("Solver")
      .vars({"solutions":"List<Solution>"})
      .init([], [
        SelfSet("solutions", New("List")),
      ])
      .func("addSolution", ["solution"], [
        #DotCall(SelfGet("solutions"), "append", [Get("solution")]),
        DotCall(SelfGet("solutions"), "append", [Get("solution")]), #just for testing
      ])
      .func("trySolve", ["problem", "universe"], [
        Var("solutions", SelfCall("getDoableSolutions", [Get("problem"), Get("universe")])),
        Var("messages", New("List")),
        ForEach("solution", DotCall(Get("solutions"), "getItems"), [
          DotCall(Get("messages"), "append", [Concat([DotCall(Get("solution"), "toString"), Const("\n")])])
        ]),
        #Return(SelfCall("getDoableSolutions", [Get("problem"), Get("universe")]))
        Return(Get("messages"))
      ])
      .func("getRelevantDirectSolutions", ["problem"], [
        Var("relevantSolutions", New("List")),
        ForEach("candidateSolution", DotCall(SelfGet("solutions"), "getItems"), [
          If(DotCall(DotGet(Get("candidateSolution"), "problem"), "equals", [Get("problem")])).then([
            DotCall(Get("relevantSolutions"), "append", [Get("candidateSolution")])
          ]),
        ]),
        Return(Get("relevantSolutions"))
      ])
      .func("getDoableSolutions", ["problem", "universe"], [
        Var("relevantSolutions", SelfCall("getRelevantDirectSolutions", [Get("problem")])),
        Var("doableSolutions", New("List")),
        ForEach("candidateSolution", DotCall(Get("relevantSolutions"), "getItems"), [
          Var("prereq", DotGet(Get("candidateSolution"), "prerequisite")),
          Var("prereqState", DotCall(Get("prereq"), "evaluate", [Get("universe")])),
          If(Eq(Get("prereqState"), Const(True))).then([
            #found a solution whose prerequisite is met
            DotCall(Get("doableSolutions"), "append", [Get("candidateSolution")]),
          ]).otherwise([
            If(Eq(Get("prereqState"), Const(None))).then([
              #found a solution for which we don't know if the prerequisite is met
              DotCall(Get("doableSolutions"), "append", [Get("candidateSolution")]),
            ]).otherwise([
              #found a solution for which the prerequisites are not met
              Var("childSolutions", SelfCall("getDoableSolutions", [Get("problem"), Get("universe")])),
              ForEach("childSolution", Get("childSolutions"), [
                DotCall(Get("doableSolutions"), "append", [Get("childSolution")]),
              ])
            ]),
          ]),
        ]),
        Return(Get("doableSolutions")),
      ]),

    Func("makeSolver", [], [
      Var("solver", New("Solver")),

      #prerequisites of solutions
      Var("doesXWork", New("TextProposition", [Const("Does X work?")])),
      Var("didYouFindHelp", New("TextProposition", [Const("Can you find a knowledgeable entity for this topic?")])),
      Var("doYouUnderstandTheProblem", New("TextProposition", [Const("Do you understand the problem?")])),
      Var("didYouFindHelpfulLogs", New("TextProposition", [Const("Did you find logs that are sufficiently helpful?")])),
      Var("canYouFindAnyLogs", New("TextProposition", [Const("Did you find any logs?")])),
      Var("canYouFindAVersionThatWorks", New("TextProposition", [Const("Can you find a version that works?")])),
      Var("canYouAffordToWait", New("TextProposition", [Const("Can you afford to wait?")])),
      Var("doYouHaveGoodSourceCode", New("TextProposition", [Const("Do you have easy-to-understand source code?")])),
      Var("doYouHaveAnySourceCode", New("TextProposition", [Const("Do you have any source code?")])),
      Var("doYouUnderstandTheSourceCode", New("TextProposition", [Const("Do you understand the source code?")])),
      Var("doYouHaveAnInstantMessenger", New("TextProposition", [Const("Do you have an instant messenger?")])),
      Var("doYouHaveInternet", New("TextProposition", [Const("Do you have internet access?")])),
      
      #problems (propositions with desired values)
      Var("xWorks", New("Problem", [Get("doesXWork"), Const(True)])),
      Var("youDidFindHelp", New("Problem", [Get("didYouFindHelp"), Const(True)])),
      Var("youDoUnderstandTheProblem", New("Problem", [Get("doYouUnderstandTheProblem"), Const(True)])),
      Var("youDidFindHelpfulLogs", New("Problem", [Get("didYouFindHelpfulLogs"), Const(True)])),
      Var("youDoHaveGoodSourceCode", New("Problem", [Get("doYouHaveGoodSourceCode"), Const(True)])),
      Var("youDoUnderstandTheSourceCode", New("Problem", [Get("doYouUnderstandTheSourceCode"), Const(True)])),

      #fixes
      Var("askForHelp", New("TextAction", [Const("Ask the knowledgeable entity for help.")])),
      Var("justSolveIt", New("TextAction", [Const("Now that you understand the problem, just solve it.")])),
      Var("readTheLogs", New("TextAction", [Const("Read the logs.")])),
      Var("haveMeAnalyzeTheLogs", New("TextAction", [Const("Have me analyze the logs (this isn't implemented yet).")])),
      Var("diffThem", New("TextAction", [Const("Look for differences using the bash command `diff -r directory1 directory2`.")])),
      Var("waitUntilYouFeelRefreshed", New("TextAction", [Const("Take a break and return with a possibly fresh perspective.")])),
      Var("waitUntilItHappensAgain", New("TextAction", [Const("Wait for the problem to happen again, at which point you might be more able to notice a pattern.")])),
      Var("rerunTheProgram", New("TextAction", [Const("Run the program again.")])),
      Var("improveTheSourceCode", New("TextAction", [Const("Improve the source code.")])),
      Var("readTheSourceCode", New("TextAction", [Const("Read the source code.")])),
      Var("readTheInstantMessengerNames", New("TextAction", [Const("Look at the names in the instant messenger.")])),
      Var("openGoogle", New("TextAction", [Const("Open google.com in a web browser.")])),
      Var("openCompanyWiki", New("TextAction", [Const("Open the company wiki in a web browser.")])),
      Var("runGitLog", New("TextAction", [Const("Run `git log <filename>`.")])),

      #You can make x work if you can find a knowledgeable entity and ask the knowledgeable entity for help
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("xWorks"), Get("didYouFindHelp"), Get("askForHelp")])]),
      #You can make X work if you you understand the problem and simply fix it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("xWorks"), Get("doYouUnderstandTheProblem"), Get("justSolveIt")])]),

      #You can understand the problem if you read some helpful logs
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheProblem"), Get("didYouFindHelpfulLogs"), Get("readTheLogs")])]),
      #You can understand the problem if I analyze some logs
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheProblem"), Get("canYouFindAnyLogs"), Get("haveMeAnalyzeTheLogs")])]),
      #You can understand the problem if you diff with a version that works
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheProblem"), Get("canYouFindAVersionThatWorks"), Get("diffThem")])]),
      #You can understand the problem if you wait until you feel better
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheProblem"), Get("canYouAffordToWait"), Get("waitUntilYouFeelRefreshed")])]),
      #You can understand the problem if you wait until it happens again
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheProblem"), Get("canYouAffordToWait"), Get("waitUntilItHappensAgain")])]),

      #You can have clear logs if you have good source code and rerun the program
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDidFindHelpfulLogs"), Get("doYouHaveGoodSourceCode"), Get("rerunTheProgram")])]),

      #You can have good source code if you understand the source code and you improve the source code
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoHaveGoodSourceCode"), Get("doYouUnderstandTheSourceCode"), Get("improveTheSourceCode")])]),

      #You can understand the source code if have the source code and you read it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDoUnderstandTheSourceCode"), Get("doYouHaveAnySourceCode"), Get("readTheSourceCode")])]),

      #You can find a knowledgeable entity if you have an instant messenger and look at the names inside it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDidFindHelp"), Get("doYouHaveAnInstantMessenger"), Get("readTheInstantMessengerNames")])]),
      #You can find a knowledgeable entity if you have internet and you open google.com
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDidFindHelp"), Get("doYouHaveInternet"), Get("openGoogle")])]),
      #You can find a knowledgeable entity if you have internet and you open the company wiki
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDidFindHelp"), Get("doYouHaveInternet"), Get("openCompanyWiki")])]),
      #You can find a knowledgeable entity if you have source code and run 'git log'
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("youDidFindHelp"), Get("doYouHaveAnySourceCode"), Get("runGitLog")])]),

      Return(Get("solver")),

      Var("solutionA", New("Solution", [Get("youDidFindHelp"), Get("doYouHaveAnySourceCode"), Get("runGitLog")])),
      #Print(Const("sol a")),
      #Print(DotCall(DotGet(Get("solutionA"), "problem"), "__str__")),
      #Print(DotCall(Get("solutionA"), "__str__")),

    ]),



    Var("solver", Call("makeSolver")),

    Print(Const("Solutions:")),
    Print(DotCall(DotGet(Get("solver"), "solutions"), "toString")),
    #Explain(DotCall(DotGet(Get("solver"), "solutions"), "__str__")),
    #Print(DotGet(Get("solver"), "solutions")),
    Print(Const("done")),


    Print(Const("Relevant solutions:")),
    #ShortExplain(DotCall(DotCall(Get("solver"), "trySolve", [Get("problem1"), Get("universe")]), "toString")),
    Print(Const("done")),

    #talks to the user, answers "why", forwards requests onto the Solver
    Class("Communicator")
      .init([], [
        SelfSet("universe", New("Universe")),
      ])
      .vars({"universe": "Universe"})
      .func("talkOnce", ["input"], [
        Var("justificationId", Int(Get("input"))),
        Print(Const("")),
        #Print(Const("responding")),

        If(Eq(Get("justificationId"), Const(None))).then([
          Var("problem1", New("Problem", [New("TextProposition", [Get("input")]), Const(True)])),
          Var("universe", SelfGet("universe")),
          Print(Const("Relevant solutions:")),
          ShortExplain(DotCall(DotCall(Get("solver"), "trySolve", [Get("problem1"), Get("universe")]), "toString"), Const(1)),
          Print(Const("End of relevant solutions")),
        ]).otherwise([
          ShortExplain(JustificationGetter(Get("justificationId")), Const(2)),
        ]),
      ])
      .func("communicate", [], [
        Print(Const("")),
        Var("response", Ask(Const("Say something!"))),
        DotCall(Get("self"), "talkOnce", [Get("response")]),
        DotCall(Get("self"), "communicate", []),
      ]),

    Var("communicator", New("Communicator")),
    DotCall(Get("communicator"), "communicate"),
  ])
  execution = Execution(program)
  execution.run()
  #suggestion = execution.getScope().getInfo("suggestion")
  #logger.message("Program result value = " + str(suggestion.value) + " because " + str(suggestion.justification.explainRecursive()))


def treeProgram():
  program = Program()
  program.put([
    #prompt the user for a bool
    Func("readBool", ["prompt"], [
      Var("response", Ask(Get("prompt"))),
      If(Eq(Get("response"), Const("Yes"))).then([
        Return(Const(True))
      ]).otherwise([
        If(Eq(Get("response"), Const("yes"))).then([
          Return(Const(True))
        ]).otherwise([
          If(Eq(Get("response"), Const("y"))).then([
            Return(Const(True))
          ]).otherwise([
            Return(Const(False))
          ])
        ])
      ])
    ]),

    Var("suggestion", Const(None)),

    #see if the user should read the logs
    Var("didReadLogs", Call("readBool", [Const("Have you read the logs?")])),
    If(Eq(Get("didReadLogs"), Const(False))).then([
      Var("canFindTheLogs", Call("readBool", [Const("Do you know where to find logs?")])),
      If(Get("canFindTheLogs")).then([
        Set("suggestion", Const("Read the logs."))
      ]).otherwise([
        Var("triedFindingLogs", Call("readBool", [Const("Have you spent at least 1 hour trying to find the logs?")])),
        If(Get("triedFindingLogs")).otherwise([
          Set("suggestion", Const("Your new subtask is to try to read the logs. Note that you can ask me for help with that task too."))
        ])
      ])
    ]),

    #some more suggestions
    If(Eq(Get("suggestion"), Const(None))).then([
      Var("haveYouGoogledIt", Call("readBool", [Const("Have you googled it?")])),
      If(Get("haveYouGoogledIt")).then([
        Var("haveYouAskedSomeone", Call("readBool", [Const("Have you asked a human for help?")])),
        If(Get("haveYouAskedSomeone")).otherwise([
          Set("suggestion", Const("Ask someone"))
        ])
      ]).otherwise([
        Set("suggestion", Const("Google it"))
      ])
    ]),

    If(Eq(Get("suggestion"), Const(None))).then([
      Set("suggestion", Const("I'm not sure"))
    ])
  ])
  execution = Execution(program)
  execution.run()
  suggestion = execution.getScope().getInfo("suggestion")
  logger.message("Program result value = " + str(suggestion.value) + " because " + str(suggestion.justification.explainRecursive()))

def inheritanceTest():
  program = Program()
  program.put([
    Class("TestGrandParent")
      .init([], [
        Print(Const("running init in TestGrandParent class"))
      ])
      .func("talk", [], [
        Print(Const("running talk in TestGrandParent class")),
      ]),
    Class("TestParent")
      .inherit("TestGrandParent")
      .init([], [
        Print(Const("running init in TestParent class")),
        SuperCall("__init__"),
        SelfCall("talk")
      ])
      .func("talk", [], [
        Print(Const("running talk in TestParent class")),
        SuperCall("talk"),
      ]),
    Class("TestChild")
      .inherit("TestParent")
      .init([], [
        Print(Const("running init in TestChild class")),
        SuperCall("__init__"),
      ])
      .func("talk", [], [
        Print(Const("running talk in TestChild class")),
        SuperCall("talk"),
      ]),

    Var("testChild", New("TestChild")),
  ])
  program.run()
  return program

def argTest():
  program = Program()
  program.put([
    Class("ArgTester")
      .vars({"key1":"string", "key2":"int"})
      .init(["key2"], [
        Print(SelfGet("key1")),
        Print(SelfGet("key2"))
      ]),

    Var("a", New("ArgTester", [Const("abcd")])),
  ])
  return program

def printModified():
  program = make_fileModified_expression()
  info = program.process()
  logger.message()
  if (info.value):
    logger.message("I do not think you have modified me. Here's why:")
  else:
    logger.message("I think you have modified me. Here's why:")
  logger.message()
  logger.message(info.justification.explainRecursive())

def main():
  #printModified()
  #equalityCheck()
  suggestion()
  #inheritanceTest()

main()
#abbdf4f9d3a6cbd25076cd554f102355 *-