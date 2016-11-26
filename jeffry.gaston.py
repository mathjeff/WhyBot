# Sorry about writing this program in Python instead of a language supporting static typing such as C#, Java or Groovy
# I wanted this program to be trivially easy to download, run, edit, and rerun, rather than just fairly easy
# Hopefully I'll rewrite this program in another language eventually

from __future__ import print_function
import inspect
import subprocess
import traceback
import sys
import collections

#############################################################################################################################################################################################
#For determining where in this file (jeffry.gaston.py) we are
#Has to be at the top of this file because it needs to be able to ignore itself when giving line numbers

class ExternalStackInfo(object):
  def __init__(self):
    self.ignoredLineNumbers = set()

  def ignoreCurrentlyActiveLines(self):
    #make a note of the current stack to enable ignoring any lines currently active (which just participate in this custom interpreter and aren't part of the program being defined)
    frame = inspect.currentframe()
    while frame is not None:
      self.ignoreLineNumber(frame.f_lineno)
      frame = frame.f_back

  def ignoreRange(self, minInclusive, maxExclusive):
    for lineNumber in range(minInclusive, maxExclusive):
      self.ignoreLineNumber(lineNumber)

  def ignoreLineNumber(self, lineNumber):
    if lineNumber not in self.ignoredLineNumbers:
      self.ignoredLineNumbers.add(lineNumber)
    
  def get_root_relevantLineNumber(self):
    #Return the line in the call stack closest to the root, excluding ignored lines
    #Generally only relevant if statements are being added to the Program
    lineNumber = None
    frame = inspect.currentframe()
    while frame is not None:
      currentLineNumber = frame.f_lineno
      if currentLineNumber not in self.ignoredLineNumbers:
        lineNumber = currentLineNumber
      frame = frame.f_back
    if lineNumber is None:
      raise Exception("Failed to identify interesting line number in the above stack trace")
    return lineNumber

  def get_leaf_relevantLineNumber(self):
    #Return the number of the line closest to the leaf, excluding ignored lines
    #Generally relevant while the Program is executing
    frame = inspect.currentframe()
    while frame is not None:
      lineNumber = frame.f_lineno
      if lineNumber not in self.ignoredLineNumbers:
        del frame
        return lineNumber
      frame = frame.f_back
    raise Exception("Failed to identify interesting line number in the above stack trace")

externalStackInfo = ExternalStackInfo()

#we're not interested in including earlier numbers in the stack trace
externalStackInfo.ignoreRange(0, externalStackInfo.get_root_relevantLineNumber())


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

def simpleDebug():
  logger.message()
  logger.message()
  message = "Rudimentary debugger called due to an error"
  boundary = "*" * len(message)
  logger.message(boundary)
  logger.message(message)
  logger.message(boundary)
  logger.message("Recall that if the above information isn't enough, then it may be worthwhile to add better debug messages and rerun this program")
  logger.message()
  logger.message("Type a number to view an explanation of the statement with that id")
  while True:
    text = raw_input("id:")
    num = int(text)
    justification = justificationsById[num]
    logger.message(justification.explainRecursive(1))

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
      explanation = justification.explainRecursive(2)
      self.message(explanation)
    self.message()
    self.message("Error stacktrace:")
    traceback.print_stack()
    if justification is not None:
      simpleDebug()
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
#program statements


#a program
class Program(object):
  def __init__(self):
    externalStackInfo.ignoreCurrentlyActiveLines()
    self.statements = []
    self.nativeClasses = [
      NativeClassDefinition("String", (lambda why, text: StringWrapper(why, text)), [
        NativeMethodDefinition("split", ["separator"]),
        NativeMethodDefinition("toString", []),
        NativeMethodDefinition("plus", ["other"]),
        NativeMethodDefinition("exceptPrefix", ["other"]),
        NativeMethodDefinition("equals", ["other"]),
      ]),
      NativeClassDefinition("List", (lambda why: ListWrapper(why)), [
        NativeMethodDefinition("append", ["item"]),
        NativeMethodDefinition("clear", []),
        NativeMethodDefinition("get", ["index"]),
        NativeMethodDefinition("tryGet", ["index"]),
        NativeMethodDefinition("removeAt", ["index"]),
        NativeMethodDefinition("getLength", []),
        NativeMethodDefinition("toString", []),
      ]),
      NativeClassDefinition("Dict", (lambda why: DictionaryWrapper(why)), [
        NativeMethodDefinition("get", ["key"]),
        NativeMethodDefinition("put", ["key", "value"]),
        NativeMethodDefinition("containsKey", ["key"]),
      ]),
      NativeClassDefinition("Bool", (lambda why, value: BoolWrapper(why, value)), [
        NativeMethodDefinition("toString", []),
        NativeMethodDefinition("equals", ["other"]),
      ]),
      NativeClassDefinition("Num", (lambda why, value: NumberWrapper(why, value)), [
        NativeMethodDefinition("toString", []),
        NativeMethodDefinition("nonEmpty", []),
        NativeMethodDefinition("equals", ["other"]),
      ]),
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
      raise Exception("Variable '" + key + "' already defined in " + str(self))
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
    calledChild_justification = AndJustification("called " + str(f.functionName), [callJustification])
    calledChild_justification.logicLocation = f.lineNumber
    #run all the statements in the function
    self.execution.runStatements(f.statements, calledChild_justification)
    self.execution.removeScope()
    result = child.tryGetInfo("return") #not sure yet whether using a variable named 'return' is a hack or a feature but it's weird
    if result is not None:
      functionText = str(f) + "(" + ", ".join([str(info.value) for info in justifiedValues]) + ")"
      if not isinstance(result, JustifiedValue):
        logger.fail("Invalid value " + repr(result.__class__) + " (not JustifiedValue) returned from " + functionText, result.justification)
      value = result.value
      if value is not None:
        if not isinstance(value, Object):
          logger.fail("Invalid value " + repr(value.__class__) + " (not Object) returned from " + functionText, result.justification)
      return result
    else:
      scope = child.tryFindScope("return")
      if scope is None:
        return JustifiedValue(None, TextJustification(str(f.functionName) + " did not reach any return statement"))
      else:
        return JustifiedValue(None, TextJustification(str(f.functionName) + " explicitly returned None"))



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
    


  def newObject(self, className, justifiedArguments, callJustification):
    classInfo = self.tryGetInfo(className)
    if classInfo is None:
      logger.fail("Class " + str(className) + " is not defined", callJustification)
    classDefinition = classInfo.value

    parentClassName = classDefinition.parentClassName
    newObject = classDefinition.newInstance(self, justifiedArguments, callJustification)

    newObject.description = className + "@" + str(newObject.objectId)

    justification = AndJustification("newObject " + str(className) + "(" + ", ".join([str(info.value) for info in justifiedArguments]) + ")",  [callJustification] + [info.justification for info in justifiedArguments])
    return JustifiedValue(newObject, justification)

  def newBoringObject(self, className, justifiedArguments, callJustification):
    resultInfo = self.newObject(className, justifiedArguments, callJustification)
    resultInfo.justification.interesting = False
    return resultInfo

  def newManagedObject(self, classDefinition, justifiedArguments, callJustification):
    if not isinstance(justifiedArguments, list):
      logger.fail("Invalid parameter type, required list, got " + str(justifiedArguments))
    newObject = self.newChild()
    #put empty values onto the object
    self.makeEmptyFields(classDefinition, newObject)
    implScope = classDefinition.implementedInScope

    self.attachClassDefinition(newObject, classDefinition)

    initInfo = classDefinition.implementedInScope.tryGetInfo("__init__")
    if initInfo is not None:
      #after having used the scope of the class to find the function, now use the execution scope to actually call that function
      executionScope = self
      executionScope.callFunction(initInfo.value, [JustifiedValue(newObject, TextJustification("my program specified a " + str(classDefinition.className)))] + justifiedArguments, callJustification)
    else:
      if len(justifiedArguments) != 0:
        logger.fail("Incorrect number of arguments; required 0, received " + str(justifiedArguments), callJustification)
    return newObject

  def newNativeObject(self, classDefinition, justifiedArguments, callJustification):
    try:
      newObject = functionUtils.unwrapAndCall(classDefinition.constructor, [callJustification] + justifiedArguments)
    except Exception as e:
      logger.fail("failed to create " + str(classDefinition) + " with args " + str([info.value for info in justifiedArguments]), AndJustification(str(e), [callJustification]))
    self.attachClassDefinition(newObject, classDefinition)
    newObject.execution = self.execution
    return newObject

  def attachClassDefinition(self, newObject, classDefinition):
    newObject.declareInfo("__class__", JustifiedValue(classDefinition, TextJustification("This is the class of the object")))
    




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

  #def toString(self, callJustification):
  #  return JustifiedValue(str(self), UnknownJustification())

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
    self.classScope = None
    self.statements = [statement for statement in program.statements]
    self.declareNativeClasses(program.nativeClasses)
    self.callStack = [None]

  def run(self):
    return self.runStatements(self.statements)

  def runStatements(self, statements, callJustification=None):
    result = None
    for statement in statements:
      self.ownStatement(statement)
    self.callStack.append(None)
    for statement in statements:
      if callJustification is not None:
        justification = callJustification
      else:
        justification = TextJustification(str(statement) + " is in my program")
      self.callStack[-1] = statement.lineNumber
      result = statement.process(justification)
      if result is not None:
        result.justification.logicLocation = self.callStack[-1]
    del self.callStack[-1]
    return result

  def ownStatement(self, statement):
    statement.beOwned(self)
    for child in statement.getChildren():
      if not hasattr(child, "beOwned"):
        raise Exception("Invalid child statement " + str(child) + " of class " + str(child.__class__) + " is of invalid class (does not implement beOwned) to be assigned to parent statement " + str(statement))
      self.ownStatement(child)

  def getScope(self):
    return self.scopes[-1]

  def newScope(self):
    scope = self.rootScope.newChild("scope at depth " + str(len(self.scopes)))
    self.addScope(scope)
    return self.getScope()

  def setClassScope(self, classScope):
    self.classScope = classScope

  def getClassScope(self):
    return self.classScope

  def addScope(self, newScope):
    self.scopes.append(newScope)

  def removeScope(self):
    self.scopes = self.scopes[:-1]

  def declareNativeClasses(self, nativeClassDefinitions):
    for nativeClassDefinition in nativeClassDefinitions:
      self.declareNativeClass(nativeClassDefinition)

  def declareNativeClass(self, nativeClassDefinition):
    externalStackInfo.ignoreCurrentlyActiveLines()
    foundInScope = self.getScope()
    managedClassName = nativeClassDefinition.managedClassName


    parentClassName = nativeClassDefinition.parentClassName
    if parentClassName is not None:
      parentClass = self.getScope().getInfo(parentClassName).value
      parentImplementationScope = parentClass.implementedInScope
    else:
      parentClass = None
      parentImplementationScope = self.rootScope
    
    implementedInScope = parentImplementationScope.newChild(nativeClassDefinition.managedClassName)
    nativeClassDefinition.implementedInScope = implementedInScope

    foundInScope.declareInfo(managedClassName, JustifiedValue(nativeClassDefinition, TextJustification(str(managedClassName) + " is a built-in class")))
    for methodDefinition in nativeClassDefinition.methodDefinitions:
      nativeStatement = NativeSelfCall(methodDefinition.methodName, [Get(argumentName) for argumentName in methodDefinition.argumentNames])
      implementedInScope.declareFunction(
        FunctionDefinition(
          methodDefinition.methodName,
          ["self"] + methodDefinition.argumentNames,
          None,
          [nativeStatement]
        ),
        TextJustification(str(methodDefinition.methodName) + " is a built-in method")
      )
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
    self.setClassScope(implementedInScope)
    self.runStatements(classDefinition.methodDefiners)
    self.setClassScope(None)
    self.removeScope()

  def putLineNumber(self, justification):
    justification.logicLocation = self.callStack[-1]

#classes relating to programming
class LogicStatement(object):
  def __init__(self):
    self.execution = None
    self.children = []
    self.classDefinitionScope = None
    self.lineNumber = externalStackInfo.get_root_relevantLineNumber()
    
  def beOwned(self, execution):
    self.execution = execution
    if self.classDefinitionScope is None:
      self.classDefinitionScope = execution.getClassScope()

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
    #childJustification = FullJustification(str(self), result.value, self.lineNumber, callJustification, [result.justification])
    childJustification = result.justification
    if result.value.isTrue():
      self.execution.runStatements(self.trueEffects, childJustification)
    else:
      self.execution.runStatements(self.falseEffects, childJustification)

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
    self.lineNumber = self.valuesProvider.lineNumber #show the line number of the top of the loop, rather than the line number of the bottom of the loop

  def process(self, callJustification):
    loopScope = self.execution.getScope().newChild("for loop of " + str(self.variableName))
    self.execution.addScope(loopScope)
    valueInfos = self.valuesProvider.process(callJustification)
    valuesJustification = valueInfos.justification
    loopScope.declareInfo(self.variableName, JustifiedValue(None, TextJustification("Initialized by ForEach loop")))
    values = valueInfos.value
    for valueInfo in values.getItems():
      value = valueInfo.value
      justification = FullJustification("loop iterator " + str(self.variableName), value, self.lineNumber, callJustification, [valuesJustification, valueInfo.justification])

      loopScope.setInfo(self.variableName, JustifiedValue(value, justification))

      iterationScope = self.execution.getScope().newChild("iteration where " + str(self.variableName) + " = " + str(value))
      self.execution.addScope(iterationScope)

      self.execution.runStatements(self.statements, justification)

      self.execution.removeScope()

    self.execution.removeScope()

  def __str__(self):
    return "for " + str(self.variableName) + " in " + str(self.valuesProvider)

#a 'for'
class For(ForEach):
  def __init__(self, variableName, lowProvider, highProvider, statements):
    valuesProvider = Range(lowProvider, highProvider)
    super(For, self).__init__(variableName, valuesProvider, statements)


#a 'while'
class While(LogicStatement):
  def __init__(self, condition, statements):
    super(While, self).__init__()
    if not hasattr(condition, "process"):
      logger.fail("Invalid condition " + str(condition) + " does not have a 'process' method")
    self.condition = condition
    self.statements = statements
    self.children.append(condition)
    self.children += statements
    self.statements = statements

  def process(self, callJustification):
    while True:
      loopScope = self.execution.getScope().newChild("while (" + str(self.condition) + ")")
      self.execution.addScope(loopScope)

      conditionInfo = self.condition.process(callJustification)
      if not conditionInfo.value:
        break

      justification = FullJustification(str(self.condition), conditionInfo.value, self.lineNumber, callJustification, [conditionInfo.justification])

      self.execution.runStatements(self.statements, justification)

      self.execution.removeScope()

  def __str__(self):
    return "while (" + str(self.condition) + ")"


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
  def __init__(self, functionName, argumentNames, lineNumber, statements):
    self.functionName = functionName
    self.argumentNames = argumentNames
    self.lineNumber = lineNumber
    self.statements = statements
    
  def __str__(self):
    return self.functionName

#a function definition
class Func(LogicStatement):
  def __init__(self, signature, statements):
    super(Func, self).__init__()
    self.functionName = signature.functionName
    if not isinstance(signature.argumentNames, list):
      raise Exception("Invalid argument " + str(signature.argumentNames) + "; must be a list")
    self.argumentNames = signature.argumentNames
    self.statements = []
    self.lineNumber = signature.lineNumber
    self.addStatements(statements)

  def process(self, justification):
    self.execution.getScope().declareFunction(FunctionDefinition(self.functionName, self.argumentNames, self.lineNumber, self.statements), justification)

  def addStatements(self, statements):
    self.statements += statements
    self.children += statements
    return self

  def __str__(self):
    return "def " + str(self.functionName)

#a definition of the signature of a method
class Sig(object):
  def __init__(self, functionName, argumentNames=[]):
    self.functionName = functionName
    self.argumentNames = argumentNames
    self.lineNumber = externalStackInfo.get_root_relevantLineNumber()

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

justification_startLine = externalStackInfo.get_root_relevantLineNumber()
#class telling why something happened
class Justification(object):
  def __init__(self):
    global justificationId
    self.supporters = []
    self.justificationId = justificationId
    justificationId += 1
    justificationsById.append(self)
    self.interesting = True
    self.implementationLocation = externalStackInfo.get_leaf_relevantLineNumber()
    self.logicLocation = None

  def addSupporter(self, supporter):
    if not isinstance(supporter, Justification):
      logger.fail("Invalid justification " + str(supporter) + " (not a subclass of Justification) given as support for " + str(self), self)
    if supporter.justificationId > self.justificationId:
      logger.fail("Added a supporter (" + str(supporter) + ") with higher id to the supportee (" + str(self) + ")")
    self.supporters.append(supporter)
    if self.logicLocation is None:
      self.logicLocation = supporter.logicLocation

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
    return self.getIdText() + self.describe()

  def getIdText(self):
    return "- (#" + str(self.justificationId) + ") "

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
      logger.fail("Invalid description (probably invalid class) passed to AndJustification: " + description, self)

  def describe(self):
    description = "[lines " + str(self.implementationLocation) + "/" + str(self.logicLocation) + "]: "
    description += str(self.description)
    return description

  
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
    message += "[lines " + str(self.implementationLocation) + "/" + str(self.logicLocation) + "]: "
    message += stringUtils.toVariableText(self.variableName) + " = " + str(self.value)
    return message

  def getInterestingChildren(self):
    if self.interesting:
      return super(FullJustification, self).getInterestingChildren()
    else:
      #if this justification is not interesting, then the reason that it was called isn't interesting either - only recurse into children that supply values
      results = []
      for child in self.valueJustifications:
        if child.interesting:
          results.append(child)
        else:
          for descendent in child.getInterestingChildren():
            if descendent not in results:
              results.append(descendent)
      return results


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


justification_endLine = externalStackInfo.get_root_relevantLineNumber()
#we're not interested in listing line numbers for the code of the Justification class, but we will be interested in listing line numbers for code that creates a Justification instance
externalStackInfo.ignoreRange(justification_startLine, justification_endLine)

#contains a value and a justification
class JustifiedValue(object):
  def __init__(self, value, justification):
    if value is not None and isinstance(value, JustifiedValue):
      logger.fail("JustifiedValue (" + str(value) + ") was given as the value of a JustifiedValue, which is unnecessary redundancy")
    self.value = value
    if not isinstance(justification, Justification):
      logger.fail("Invalid justification " + repr(justification) + " (not a subclass of Justification) given for " + str(value))
    self.justification = justification

  def __str__(self):
    return str(self.value)

  def __repr__(self):
    return str(self)

#############################################################################################################################################################################################
#Things relating to value providers

#abstract class that returns a value
class ValueProvider(object):
  def __init__(self):
    self.execution = None
    self.lineNumber = externalStackInfo.get_root_relevantLineNumber()
    self.classDefinitionScope = None
    
  def beOwned(self, execution):
    self.execution = execution
    if self.classDefinitionScope is None:
      self.classDefinitionScope = execution.getClassScope()

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

  def process(self, callJustification):
    inputInfo = self.inputProvider.process(callJustification)
    outputValue = None
    inputText = inputInfo.value
    if inputText is not None:
      try:
        outputValue = int(inputText.getText())
      except ValueError as e:
        pass
    return self.execution.getScope().newObject("Num", [JustifiedValue(outputValue, UnknownJustification())], callJustification)
    #justification = FullJustification("int(" + str(inputInfo.value) + ")", outputObject, self.lineNumber, callJustification, [inputInfo.justification])
    #return JustifiedValue(outputObject, justification)

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
      justification = justificationsById[value.getNumber()]
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
    super(Ask, self).__init__()
    self.promptProvider = promptProvider

  def process(self, callJustification):
    if self.promptProvider is not None:
      prompt = self.promptProvider.process(callJustification).value.getText()
    else:
      prompt = ''
    try:
      enteredText = raw_input(prompt)
    except EOFError as e:
      sys.exit(0)
    message = "You entered '" + str(enteredText) + "'"
    if prompt is not None:
      message += " when asked '" + str(prompt) + "'"
    return self.execution.getScope().newObject("String", [JustifiedValue(enteredText, UnknownJustification())], TextJustification(message))

  def getChildren(self):
    result = []
    if self.promptProvider is not None:
      result.append(self.promptProvider)
    return result

  def __str__(self):
    return str(self.promptProvider)

#tells whether two things are equal
class Eq(ValueProvider):
  def __init__(self, provider1, provider2):
    super(Eq, self).__init__()
    self.provider1 = provider1
    self.provider2 = provider2
      

  def process(self, callJustification):
    info1 = self.provider1.process(callJustification)
    info2 = self.provider2.process(callJustification)
    if info1.value is not None:
      value1 = info1.value
    else:
      value1 = None
    if info2.value is not None:
      value2 = info2.value
    else:
      value2 = None
    if value1 is not None and isinstance(value1, Object):
      logger.fail("Invalid value1 is instanceof Object (" + str(value1) + " of class " + str(value1.__class__) + ") provided to Eq. An Object should provide a proper 'equals' method to use instead", info1.justification)
    if value2 is not None and isinstance(value2, Object):
      logger.fail("Invalid value2 is instanceof Object (" + str(value2) + " of class " + str(value2.__class__) + ") provided to Eq. An Object should provide a proper 'equals' method to use instead", info2.justification)
    matches = (value1 == value2)
    description = str(self.provider1)
    if matches:
      description += "="
    else:
      description += "!="
    description += str(self.provider2)
    justification1 = FullJustification(str(self.provider1), info1.value, self.lineNumber, callJustification, [info1.justification])
    justification2 = FullJustification(str(self.provider2), info2.value, self.lineNumber, callJustification, [info2.justification])
    justification = AndJustification(description, [justification1, justification2])
    justifiedValue = JustifiedValue(matches, justification)
    resultInfo = self.execution.getScope().newBoringObject("Bool", [justifiedValue], callJustification)
    return resultInfo

  def getChildren(self):
    return [self.provider1, self.provider2]

  def __str__(self):
    return str(self.provider1) + "==" + str(self.provider2)


#boolean negation (True becomes False, False becomes True)
class Not(ValueProvider):
  def __init__(self, provider):
    super(Not, self).__init__()
    self.provider = provider
      

  def process(self, callJustification):
    subInfo = self.provider.process(callJustification)
    resultValue = not subInfo.value.isTrue()
    resultInfo = self.execution.getScope().newBoringObject("Bool", [JustifiedValue(resultValue, subInfo.justification)], callJustification)

    description = str(self) + " = " + str(resultValue)

    justification = FullJustification(str(self), resultInfo.value, self.lineNumber, callJustification, [subInfo.justification])
    return JustifiedValue(resultInfo.value, justification)

  def getChildren(self):
    return [self.provider]

  def __str__(self):
    return "!(" + str(self.provider) + ")"

#tells whether an Object is None
class IsNone(ValueProvider):
  def __init__(self, provider):
    super(IsNone, self).__init__()
    self.provider = provider
      

  def process(self, callJustification):
    subInfo = self.provider.process(callJustification)
    resultValue = (subInfo.value is None)
    resultInfo = self.execution.getScope().newBoringObject("Bool", [JustifiedValue(resultValue, subInfo.justification)], callJustification)

    description = str(self) + " = " + str(resultValue)

    justification = FullJustification(str(self), resultInfo.value, self.lineNumber, callJustification, [subInfo.justification])
    return JustifiedValue(resultInfo.value, justification)

  def getChildren(self):
    return [self.provider]

  def __str__(self):
    return "(" + str(self.provider) + " == None)"


#############################################################################################################################################################################################
#gets a variable from the current scope
class Plus(ValueProvider):
  def __init__(self, valueProviders):
    super(Plus, self).__init__()
    self.valueProviders = valueProviders

  def process(self, callJustification):
    infos = [provider.process(callJustification) for provider in self.valueProviders]
    info0 = infos[0]
    sum = info0
    if not isinstance(sum.value, Object):
      logger.fail("Invalid data type for " + str(sum) + " (not object)", info0.justification)
    for otherInfo in infos[1:]:
      value = otherInfo.value
      if not isinstance(value, Object):
        logger.fail("Invalid data type for " + str(value) + " (not object)", otherInfo.justification)
      sum = sum.value.callMethodName("plus", [otherInfo], callJustification)
      if not isinstance(sum.value, Object):
        logger.fail("Invalid return data type for " + str(sum) + " (not object)", sum.justification)

    justifications = [info.justification for info in infos]
    justification = FullJustification(str(self), sum, self.lineNumber, callJustification, justifications)
    return JustifiedValue(sum.value, justification)

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

class WithId(ValueProvider):
  def __init__(self, itemProvider):
    super(WithId, self).__init__()
    self.itemProvider = itemProvider

  def process(self, callJustification):
    info = self.itemProvider.process(callJustification)
    description = info.justification.getIdText() + str(info.value)
    return self.execution.getScope().newBoringObject("String", [JustifiedValue(description, info.justification)], callJustification)

  def getChildren(self):
    return [self.itemProvider]

  def __str__(self):
    return "WithId(" + str(self.itemProvider) + ")"

#############################################################################################################################################################################################
#Some I/O

class Print(LogicStatement):
  def __init__(self, messageProvider):
    super(Print, self).__init__()
    self.messageProvider = messageProvider
    if self.messageProvider is None:
      self.messageProvider = Str("")
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
    logger.message(info.value.getText())
    return info

  def __str__(self):
    return "Print(" + str(self.messageProvider) + ")"

class PrintWithId(Print):
  def __init__(self, messageProvider):
    super(PrintWithId, self).__init__(WithId(messageProvider))

  def process(self, justification):
    info = self.messageProvider.process(justification)
    logger.message(info.value.getText())
    return info

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

  def newInstance(self, scope, justifiedArguments, callJustification):
    return scope.newManagedObject(self, justifiedArguments, callJustification)


  def __str__(self):
    return "classdef:" + str(self.className)

#declares a class
class Class(LogicStatement):
  def __init__(self, className):
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

  def func(self, functionSignature, statements):
    functionSignature.argumentNames = ["self"] + functionSignature.argumentNames
    f = Func(functionSignature, statements)
    self.methodDefiners.append(f)
    self.children.append(f)
    return self #to enable the caller to declare another function

  def init(self, argumentNames, statements):
    #If any init arguments match declared variable names, then copy them automatically. Isn't it cool inventing a new language and being able to add this kind of thing?
    valueCopierStatements = []
    for argumentName in argumentNames:
      if argumentName in self.fieldTypes:
        valueCopierStatements.append(SelfSet(argumentName, Get(argumentName)))
    return self.func(Sig("__init__", argumentNames), valueCopierStatements + statements)

  def process(self, justification):
    classDefinition = ClassDefinition(self.className, self.parentClassName, self.fieldTypes, self.methodDefiners)
    self.execution.declareClass(classDefinition, justification)
    
  def __str__(self):
    return "declare class " + str(self.className)


#makes a new object
class New(ValueProvider):
  def __init__(self, className, argumentProviders=[]):
    super(New, self).__init__()
    self.className = className
    self.argumentProviders = argumentProviders

  def process(self, callJustification):
    argumentInfos = [item.process(callJustification) for item in self.argumentProviders]
    callJustifications = [callJustification] + [item.justification for item in argumentInfos]
    numNonSelfParameters = len(callJustifications) - 1

    text = "new " + str(self.className) + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")"
    if self.execution is None:
      logger.fail("Invalid None execution on " + str(self) + " at " + str(self.lineNumber))
    result = self.execution.getScope().newObject(self.className, argumentInfos, AndJustification(text, callJustifications))
    return result

  def getChildren(self):
    return self.argumentProviders

  def __str__(self):
    return "new " + str(self.className) + "(" + ", ".join([str(item) for item in self.argumentProviders]) + ")"
    
class Str(New):
  def __init__(self, text):
    super(Str, self).__init__("String", [Const(text)])

class Bool(New):
  def __init__(self, value):
    super(Bool, self).__init__("Bool", [Const(value)])

class Num(New):
  def __init__(self, value):
    super(Num, self).__init__("Num", [Const(value)])

class Range(ValueProvider):
  def __init__(self, arg1Provider, arg2Provider=None):
    super(Range, self).__init__()
    if arg2Provider is not None:
      self.highProvider = arg2Provider
      self.lowProvider = arg1Provider
    else:
      self.highProvider = arg1Provider
      self.lowProvider = Num(0)

  def getChildren(self):
    return [self.lowProvider, self.highProvider]

	  
  def process(self, callJustification):
    lowInfo = self.lowProvider.process(callJustification)
    highInfo = self.highProvider.process(callJustification)
    outputInfo = self.execution.getScope().newBoringObject("List", [], callJustification)
    for item in range(lowInfo.value.getNumber(), highInfo.value.getNumber()):
      newItem = self.execution.getScope().newBoringObject("Num", [JustifiedValue(item, UnknownJustification())], callJustification)
      outputInfo.value.append(callJustification, newItem)
    return JustifiedValue(outputInfo.value,
             AndJustification(str(self) + " = (" + str(lowInfo.value.getNumber()) + "," + str(highInfo.value.getNumber()) + ")",
               [lowInfo.justification, highInfo.justification]))
  
  def __str__(self):
    return "range(" + str(self.lowProvider) + "," + str(self.highProvider) + ")"
	
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
    try:
      valueInfo = owner.getInfo(self.propertyName)
    except Exception as e:
      logger.fail("Failed to get " + str(self.propertyName) + ": " + str(e), callJustification)
    description = stringUtils.toGetterText(owner, self.propertyName)
    justification = FullJustification(description, valueInfo.value, self.lineNumber, callJustification, [ownerInfo.justification, valueInfo.justification])
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
    return JustifiedValue(self.classDefinitionScope, UnknownJustification())

  def __str__(self):
    return str(self.classDefinitionScope)

#returns the parent of the scope in which the current class is defined (so almost the parent's ClassDefinition)
class SuperScope(DefinedInClass_Scope):
  def __init__(self):
    super(SuperScope, self).__init__()

  def process(self, justification):
    return JustifiedValue(self.classDefinitionScope.parent, TextJustification("parent scope of " + str(self.classDefinitionScope) + " is " + str(self.classDefinitionScope.parent)))

  def __str__(self):
    return str(self.classDefinitionScope) + ".super"

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
      classInfo = objectValue.getInfo("__class__")
    except Exception as e:
      logger.fail("class lookup of " + str(objectValue) + " failed", justification)
    classDefinition = classInfo.value
    classScope = classDefinition.implementedInScope
    return JustifiedValue(classScope, TextJustification("(" + str(objectValue) + ") instanceof " + str(classDefinition)))

  def getChildren(self):
    return [self.objectProvider]

  def __str__(self):
    return "class lookup of " + str(self.objectProvider)

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
    if not isinstance(methodName, type("")):
      logger.fail("invalid method name: " + str(methodName))
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
    contextJustification = AndJustification(text, [callJustification, selfJustification, classScope_Justification] + argumentJustifications)
    contextJustification.logicLocation = self.lineNumber
    f = classScope.getFunction(self.methodName, contextJustification)
    result = self.execution.getScope().callFunction(f, argumentInfos, contextJustification)
    justification = FullJustification(str(self), result.value, self.lineNumber, callJustification, [result.justification])
    return JustifiedValue(result.value, justification)

  def __str__(self):
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
    if not isinstance(argumentProviders, list):
      logger.fail("Invalid class (" + str(argumentProviders.__class__) + ") for object " + str(argumentProviders) + ", not a list")
    super(DotCall, self).__init__(ClassFromObject_Scope(objectProvider), methodName, [objectProvider] + argumentProviders)

class FunctionUtils(object):
  def unwrapAndCall(self, method, args):
    count = len(args)
    if count == 0:
      result = method()
    elif count == 1:
      result = method(args[0])
    elif count == 2:
      result = method(args[0], args[1])
    elif count == 3:
      result = method(args[0], args[1], args[2])
    elif count == 4:
      result = method(args[0], args[1], args[2], arg[3])
    elif count == 5:
      result = method(args[0], args[1], args[2], arg[3], arg[4])
    elif count == 6:
      result = method(args[0], args[1], args[2], arg[3], arg[4], arg[5])
    elif count == 7:
      result = method(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6])
    elif count == 8:
      result = method(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6], arg[7])
    elif count == 9:
      result = method(args[0], args[1], args[2], arg[3], arg[4], arg[5], arg[6], arg[7], arg[8])
    else:
      #TODO there must be a better way to do this
      logger.fail("Too many arguments: " + str(args))
    return result
functionUtils = FunctionUtils()


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
    nativeObject = managedObject
    argumentInfos = [provider.process(callJustification) for provider in self.argumentProviders]
    argsText = "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")"
    argumentsJustification = FullJustification(self.methodName + " arguments", argsText, self.lineNumber, callJustification, [info.justification for info in argumentInfos])
    allJustifications = [callJustification] + [info.justification for info in argumentInfos]
    try:
      nativeMethod = getattr(nativeObject, self.methodName)
    except Exception as e:
      logger.fail(str(self) + " failed", AndJustification(str(e), [callJustification, argumentsJustification]))
    historyJustification = AndJustification("Called (unmanaged) " + str(managedObject) + "." + self.methodName + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")", [callJustification, selfJustification] + [argumentsJustification])
    args = [historyJustification] + [info for info in argumentInfos]
    try:
      succeeded = False
      result = functionUtils.unwrapAndCall(nativeMethod, args)
      succeeded = True
    finally:
      if not succeeded:
        logger.message(str(self) + " failed")
    if result is None:
      result = JustifiedValue(None, UnknownJustification())
    historyJustification.interesting = False #we don't expect the user to be interested in knowing that we made an unmanaged call to implement their code, now that the call succeeded
    justification = FullJustification("unmanaged " + str(managedObject) + "." + self.methodName + "(" + ", ".join([str(info.value) for info in argumentInfos]) + ")", result.value, self.lineNumber, callJustification, [result.justification])
    justification.interesting = False #users probably don't care to to think about how many calls we made to implement their function call
    self.execution.getScope().declareInfo("return", JustifiedValue(result.value, justification))
    return result

  def __str__(self):
    return "NativeSelfCall: " + str(self.methodName)

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

  def newInstance(self, scope, justifiedArguments, callJustification):
    return scope.newNativeObject(self, justifiedArguments, callJustification)

  def __str__(self):
    return "native classdef:" + str(self.managedClassName)

#the definition of a method that's implemented by a native method
class NativeMethodDefinition(object):
  def __init__(self, methodName, argumentNames=[]):
    self.methodName = methodName
    self.argumentNames = argumentNames
    
class NativeObject(Object):
  def __init__(self):
    super(NativeObject, self).__init__(None)
    self.managedObject = self
    self.nativeObject = self
    
class ListWrapper(NativeObject):
  def __init__(self, callJustification):
    super(ListWrapper, self).__init__()
    self.justifications = []
    self.impl = []

  def getItems(self):
    return self.impl

  def append(self, callJustification, item):
    if not isinstance(item, JustifiedValue):
      logger.fail("Invalid item " + str(item) + " (not a subclass of JustifiedValue) appended to " + str(self), callJustification)
    justification = AndJustification("appended " + str(item.value) + " to " + str(self.impl), [callJustification, item.justification])
    justification.logicLocation = callJustification.logicLocation
    self.impl.append(JustifiedValue(item.value, justification))
    return JustifiedValue(None, callJustification)

  def get(self, callJustification, indexInfo):
    index = indexInfo.value.getNumber()
    itemInfo = self.impl[index]
    item = itemInfo.value
    justification = AndJustification("returned " + str(self) + "[" + str(index) + "] = " + str(item), [itemInfo.justification, callJustification, indexInfo.justification])
    return JustifiedValue(item, justification)

  def tryGet(self, callJustification, indexInfo):
    index = indexInfo.value.getNumber()
    if index is None:
      itemJustification = TextJustification("index is None")
      item = None
    elif index >= len(self.impl):
      itemJustification = TextJustification("index (" + str(index) + ") is past the end of " + str(self) + " (" + str(len(self.impl)) + ")")
      item = None
    else:
      itemInfo = self.impl[index]
      item = itemInfo.value
      itemJustification = itemInfo.justification
    justification = AndJustification("returned " + str(self) + "[" + str(index) + "] = " + str(item), [itemJustification, callJustification, indexInfo.justification])
    return JustifiedValue(item, justification)

  def removeAt(self, callJustification, indexInfo):
    del self.impl[indexInfo.value.getNumber()]

  def getLength(self, callJustification):
    length = len(self.impl)
    justification = AndJustification("these " + str(length) + " items were added to " + str(self), [info.justification for info in self.impl])
    resultInfo = self.execution.getScope().newBoringObject("Num", [JustifiedValue(length, justification)], callJustification)
    return resultInfo

  def clear(self, callJustification):
    self.impl = []
    
  def toString(self, callJustification):
    tostringInfos = []
    textObjects = []
    allJustifications = []
    for info in self.impl:
      value = info.value
      allJustifications.append(info.justification)
      elementInfo = value.callMethodName("toString", [], callJustification)
      tostringInfos.append(elementInfo)
      textObjects.append(elementInfo.value)
    result =  "[" + ", ".join([obj.getText() for obj in textObjects]) + "]"
    justificationText  =  "Returned List.toString() = " + result
    elementsJustification = AndJustification(justificationText, [callJustification] + allJustifications)
    resultInfo = self.managedObject.execution.getScope().newBoringObject("String", [JustifiedValue(result, elementsJustification)], callJustification)
    return resultInfo

class StringWrapper(NativeObject):
  def __init__(self, callJustification, textInfo):
    super(StringWrapper, self).__init__()
    self.textInfo = textInfo
    if textInfo.value is not None and not isinstance(textInfo.value, type("")):
      logger.fail("Invalid class (not string) for " + str(textInfo))

  def toString(self, callJustification):
    return JustifiedValue(self.managedObject, callJustification)

  def split(self, callJustification, separatorInfo):
    separator = separatorInfo.value.getText()
    text = self.getText()
    outputList = text.split(separator)
    outputInfo = self.execution.getScope().newObject("List", [], callJustification)
    outputInfo.justification.interesting = False
    outputObject = outputInfo.value
    justification = AndJustification(str(self) + ".split(" + str(separator) + ") = " + str(outputList), [callJustification, self.textInfo.justification, separatorInfo.justification])
    for item in outputList:
      itemInfo = self.execution.getScope().newObject("String", [JustifiedValue(item, justification)], justification)
      itemInfo.justification.interesting = False
      outputObject.append(justification, itemInfo)
    return JustifiedValue(outputObject, justification)

  def plus(self, callJustification, other):
    if self.managedObject is None:
      logger.fail("Invalid None managedObject for " + str(self) + " from ", self.textInfo.justification)
    otherString = other.value
    try:
      text = self.textInfo.value + otherString.textInfo.value
    except Exception as e:
      logger.fail("Failed to add '" + str(self) + "' and '" + str(other) + "'", AndJustification(str(e), [callJustification]))
    justification = AndJustification("concatenation = " + str(text), [callJustification, self.textInfo.justification, otherString.textInfo.justification])
    resultInfo = self.managedObject.execution.getScope().newBoringObject("String", [JustifiedValue(text, justification)], callJustification)
    return resultInfo

  def equals(self, callJustification, otherInfo):
    ourValue = self.getText()
    other = otherInfo.value
    try:
      theirValue = other.getText()
    except Exception as e:
      logger.fail(str(self) + " == " + str(other) + " failed", AndJustification(str(e), [callJustification]))
    result = (ourValue == theirValue)
    if result:
      comparison = "=="
    else:
      comparison = "!="
    justification = AndJustification(str(ourValue) + str(comparison) + str(theirValue), [self.textInfo.justification, other.textInfo.justification])
    return self.managedObject.execution.getScope().newObject("Bool", [JustifiedValue(result, justification)], callJustification)

  def exceptPrefix(self, callJustification, prefixInfo):
    ourText = self.getText()
    prefix = prefixInfo.value
    prefixText = prefix.getText()
    if ourText.startswith(prefixText):
      resultText = ourText[len(prefixText):]
      justification = TextJustification("'" + str(ourText) + "' starts with '" + str(prefixText) + "'")
    else:
      resultText = ourText
      justification = TextJustification("'" + str(ourText) + "' does not start with '" + str(prefixText) + "'")
    return self.execution.getScope().newBoringObject("String", [JustifiedValue(resultText, justification)], callJustification)

  def getText(self):
    return self.textInfo.value
    
  def __str__(self):
    return str(self.getText())

class BoolWrapper(NativeObject):
  def __init__(self, callJustification, valueInfo):
    super(BoolWrapper, self).__init__()
    self.valueInfo = valueInfo

  def toString(self, callJustification):
    return self.managedObject.execution.getScope().newObject("String", [JustifiedValue(str(self.valueInfo.value), self.valueInfo.justification)], callJustification)

  def isTrue(self):
    if self.valueInfo.value == True:
       return True
    if self.valueInfo.value == False:
       return False
    logger.fail("Invalid (non-bool) value given to BoolWrapper: " + str(self.valueInfo.value) + " of class " + str(self.valueInfo.value.__class__), self.valueInfo.justification)

  def equals(self, callJustification, otherInfo):
    ourValue = self.isTrue()
    other = otherInfo.value
    theirValue = other.isTrue()
    result = (ourValue == theirValue)
    if result:
      comparison = "=="
    else:
      comparison = "!="
    justification = AndJustification(str(ourValue) + comparison + str(theirValue), [self.valueInfo.justification, other.valueInfo.justification])
    resultInfo = self.managedObject.execution.getScope().newBoringObject("Bool", [JustifiedValue(result, justification)], callJustification)
    return resultInfo


  def __str__(self):
    return str(self.valueInfo.value)

class DictionaryWrapper(NativeObject):
  def __init__(self, callJustification):
    super(DictionaryWrapper, self).__init__()
    self.items = {}
    self.keyInfos = collections.OrderedDict()

  def getItems(self):
    #returns List<TKey, JustifiedValue<TValue, Justification>>
    result = []
    for (key, info) in self.keyInfos.iteritems():
      result.append(info)
    return result

  def get(self, callJustification, keyInfo):
    key = keyInfo.value.getText()
    if key not in self.items:
      return JustifiedValue(None, AndJustification(str(key) + " not found in " + str(self), [callJustification]))
    info = self.items.get(key)
    return JustifiedValue(info.value, AndJustification(str(key) + " retrieved from " + str(self), [callJustification, info.justification]))

  def put(self, callJustification, keyInfo, valueInfo):
    try:
      key = keyInfo.value.getText()
    except Exception as e:
      logger.fail(str(self) + " failed to get key text from " + str(keyInfo), AndJustification(str(e), [callJustification]))
    value = valueInfo.value
    justification = AndJustification("called " + str(self) + "[" + str(key) + "] = " + str(value), [callJustification, keyInfo.justification, valueInfo.justification])
    self.items[key] = JustifiedValue(value, justification)
    self.keyInfos[key] = keyInfo
    return None

  def containsKey(self, callJustification, keyInfo):
    key = keyInfo.value.getText()
    result = (key in self.items)
    supporters = [callJustification]
    if result:
      explanationText = str(key) + " in " + str(self)
      supporters.append(self.items[key].justification)
    else:
      explanationText = str(key) + " not in " + str(self)
    justification = AndJustification(explanationText, supporters)
    resultInfo = self.execution.getScope().newBoringObject("Bool", [JustifiedValue(result, justification)], callJustification)
    return resultInfo


      
class NumberWrapper(NativeObject):
  def __init__(self, callJustification, numberInfo):
    super(NumberWrapper, self).__init__()
    self.numberInfo = numberInfo

  def getNumber(self):
    return self.numberInfo.value

  def nonEmpty(self, callJustification):
    resultBool = (self.getNumber() is not None)
    return self.managedObject.execution.getScope().newBoringObject("Bool", [JustifiedValue(resultBool, self.numberInfo.justification)], callJustification)

  def equals(self, callJustification, otherInfo):
    other = otherInfo.value
    resultBool = self.getNumber() == other.getNumber()
    justification = AndJustification(str(self.getNumber()) + " == " + str(other.getNumber()), [self.numberInfo.justification, otherInfo.justification])
    return self.managedObject.execution.getScope().newBoringObject("Bool", [JustifiedValue(resultBool, justification)], callJustification)

  def toString(self, callJustification):
    outputString = str(self.numberInfo.value)
    return self.execution.getScope().newBoringObject("String", [JustifiedValue(outputString, self.numberInfo.justification)], callJustification)

  def __str__(self):
    return str(self.numberInfo.value)



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
  return JustifiedShell(Str("stat --format %y jeffry.gaston.py  | grep -o 2016-10-05"))

def get_currentHash_expression():
  return JustifiedShell(Str("head -n `wc -l jeffry.gaston.py | sed 's/ .*//'` jeffry.gaston.py  | md5sum | sed 's/^/#/'"))

def get_savedHash_expression():
  return JustifiedShell(Str("tail -n 1 jeffry.gaston.py"))

def make_fileModified_expression():
  return Eq(get_savedHash_expression(), get_currentHash_expression())

logger = PrintLogger()

def equalityCheck():
  program = Program()
  storage = program.storage
  program.put([
    Set(storage, "a", Str("one")),
    Set(storage, "b", Str("two")),
    If(Eq(Get("a"), Get("b"))).then(
      Set(storage, "result", Str("equal")),
      Set(storage, "result", Str("different"))
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
      #magic 8-ball
        #the future's foggy now, try again later

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


    #a thing that can be done
    Class("Action")
      .func(Sig("offer", []), [
        AbstractException()
      ])
      .func(Sig("execute", []), [
        AbstractException()
      ]),

    #an Action that prints a message
    Class("TextAction")
      .vars({"message": "string"})
      .init(["message"], [
      ])
      .func(Sig("offer", []), [
        PrintWithId(SelfGet("message")),
      ])
      .func(Sig("execute", []), [
        SelfCall("offer"),
      ])
      .func(Sig("toString", []), [
        Return(SelfGet("message"))
      ]),

    Class("Universe")
      .vars({"props":"Map<string,string>"})
      .init([], [
        SelfSet("props", New("Dict")),
      ])
      .func(Sig("getProp", ["key"]), [
        Return(DotCall(SelfGet("props"), "get", [Get("key")])),
      ])
      .func(Sig("putProp", ["key", "value"]), [
        DotCall(SelfGet("props"), "put", [Get("key"), Get("value")]),
      ]),

    Class("Proposition")
      .func(Sig("evaluate", ["universe"]), [
        AbstractException()
      ]),

    #a Proposition without much logic - it just asks the Universe what its value is
    Class("TextProposition")
      .inherit("Proposition")
      .vars({"text": "String"})
      .init(["text"], [
      ])
      .func(Sig("evaluate", ["universe"]), [
        Return(DotCall(Get("universe"), "getProp", [SelfGet("text")])),
      ])
      .func(Sig("equals", ["other"]), [
        Return(DotCall(SelfGet("text"), "equals", [DotGet(Get("other"), "text")])),
      ])
      .func(Sig("toString", []), [
        Return(SelfGet("text"))
      ]),

    #a Proposition that says that two values are equal
    Class("EqualProposition")
      .inherit("Proposition")
      .vars({"left":"Proposition", "right":"Proposition"}) 
      .init(["left", "right"], [
      ])
      .func(Sig("evaluate", ["universe"]), [
        Return(Eq(
            DotCall(SelfGet("left"), "evaluate", [Get("universe")]), 
            DotCall(SelfGet("right"), "evaluate", [Get("universe")])
        )),
      ])
      .func(Sig("equals", ["other"]), [
        Var("result", Bool(False)),
        If(DotCall(SelfGet("left"), "equals", [DotGet(Get("other"), "left")])).then([
          If(DotCall(SelfGet("right"), "equals", [DotGet(Get("other"), "right")])).then([
            Set("result", Bool(True)), #we could do fancy more-accurate things like checking for inverted checks with inverted outcomes, but we're not doing that for now
          ])
        ]),
        Return(Get("result"))
      ])
      .func(Sig("toString", []), [
        Return(Concat([
          DotCall(SelfGet("left"), "toString"),
          Str(" == "),
          DotCall(SelfGet("right"), "toString"),
        ]))
      ]),

    #a problem (Proposition whose value the user wants to be True) to be solved, a way to solve it (an Action to do), and a prerequisite (a Proposition whose value could be True) required before being able to solve it
    Class("Solution")
      .vars({"problem":"Proposition", "prerequisite":"Proposition", "fix":"Action"})
      .init(["problem", "prerequisite", "fix"], [      
      ])
      .func(Sig("toString", []), [
        Return(Concat([
          Str('If "'),
          DotCall(SelfGet("prerequisite"), "toString"),
          Str('" and "'),
          DotCall(SelfGet("fix"), "toString"),
          Str('" then "'),
          DotCall(SelfGet("problem"), "toString"),
          Str('" should be all set.'),
        ]))
      ])
      .func(Sig("offer", []), [
        #Print(Concat([Str("If you can solve '"), DotCall(SelfGet("prerequisite"), "toString"), Str("':")])),
        DotCall(SelfGet("fix"), "offer"),
        #Print(Concat([Str("This should solve "), DotCall(SelfGet("problem"), "toString")])),
      ])
      .func(Sig("execute", []), [
        DotCall(SelfGet("fix"), "execute"),
      ]),

    #searches a list of solutions for a relevant solution
    Class("Solver")
      .vars({"solutions":"Map<String, List<Solution>>"})
      .init([], [
        SelfSet("solutions", New("Dict")),
      ])
      .func(Sig("addSolution", ["solution"]), [
        Var("key", DotCall(DotGet(Get("solution"), "problem"), "toString")),
        If(Not(DotCall(SelfGet("solutions"), "containsKey", [Get("key")]))).then([
          DotCall(SelfGet("solutions"), "put", [Get("key"), New("List")]),
        ]),
        DotCall(DotCall(SelfGet("solutions"), "get", [Get("key")]) , "append", [Get("solution")]),
      ])
      .func(Sig("trySolve", ["problem", "universe"]), [
        Var("solutions", SelfCall("getDoableSolutions", [Get("problem"), Get("universe")])),
        Return(Get("solutions")),
      ])
      .func(Sig("getRelevantDirectSolutions", ["problem"]), [
        Var("relevantSolutions", New("List")),
        Var("knownSolutions", DotCall(SelfGet("solutions"), "get", [DotCall(Get("problem"), "toString")])),
        If(IsNone(Get("knownSolutions"))).then([
          Return(New("List")),
        ]).otherwise([
          Return(Get("knownSolutions")),
        ])
      ])
      .func(Sig("getDoableSolutions", ["problem", "universe"]), [
        Var("relevantSolutions", SelfCall("getRelevantDirectSolutions", [Get("problem")])),
        Var("doableSolutions", New("List")),
        ForEach("candidateSolution", Get("relevantSolutions"), [
          Var("prereq", DotGet(Get("candidateSolution"), "prerequisite")),
          Var("prereqState", DotCall(Get("prereq"), "evaluate", [Get("universe")])),
          If(IsNone(Get("prereqState"))).then([
            #found a solution for which we don't know if the prerequisite is met
            DotCall(Get("doableSolutions"), "append", [Get("candidateSolution")]),
          ]).otherwise([
            If(DotCall(Get("prereqState"), "equals", [Bool(True)])).then([
              #found a solution whose prerequisite is met
              DotCall(Get("doableSolutions"), "append", [Get("candidateSolution")]),
            ]).otherwise([
              #found a solution for which the prerequisites are not met
              Var("childSolutions", SelfCall("getDoableSolutions", [Get("prereq"), Get("universe")])),
              ForEach("childSolution", Get("childSolutions"), [
                DotCall(Get("doableSolutions"), "append", [Get("childSolution")]),
              ])
            ]),
          ]),
        ]),
        Return(Get("doableSolutions")),
      ]),

    Func(Sig("makeSolver", []), [
      Var("solver", New("Solver")),

      #prerequisites of solutions
      Var("xWorks", New("TextProposition", [Str("I need my software to work")])),
      Var("didYouFindHelp", New("TextProposition", [Str("I need to find a knowledgeable entity")])),
      Var("doYouUnderstandTheProblem", New("TextProposition", [Str("I need to understand the problem")])),
      Var("didYouFindHelpfulLogs", New("TextProposition", [Str("I need helpful logs")])),
      Var("canYouFindAnyLogs", New("TextProposition", [Str("Find logs")])),
      Var("canYouFindAVersionThatWorks", New("TextProposition", [Str("Find a version that works")])),
      Var("canYouAffordToWait", New("TextProposition", [Str("Afford to wait")])),
      Var("doYouHaveGoodSourceCode", New("TextProposition", [Str("I need to have clear code")])),
      Var("doYouHaveAnySourceCode", New("TextProposition", [Str("Have any code")])),
      Var("doYouUnderstandTheSourceCode", New("TextProposition", [Str("I need to understand the code")])),
      Var("doYouHaveAnInstantMessenger", New("TextProposition", [Str("Have an instant messenger")])),
      Var("doYouHaveInternet", New("TextProposition", [Str("Have internet access")])),
      
      #fixes
      Var("askForHelp", New("TextAction", [Str("Ask a knowledgeable entity for help.")])),
      Var("justSolveIt", New("TextAction", [Str("Use your knowledge of the problem to solve it.")])),
      Var("readTheLogs", New("TextAction", [Str("Read the logs.")])),
      Var("haveMeAnalyzeTheLogs", New("TextAction", [Str("Have me analyze the logs (this isn't implemented yet).")])),
      Var("diffThem", New("TextAction", [Str("Look for differences using the bash command `diff -r directory1 directory2`.")])),
      Var("waitUntilYouFeelRefreshed", New("TextAction", [Str("Take a break and return with a possibly fresh perspective.")])),
      Var("waitUntilItHappensAgain", New("TextAction", [Str("Wait for the problem to happen again, at which point you might be more able to notice a pattern.")])),
      Var("rerunTheProgram", New("TextAction", [Str("Run the program again.")])),
      Var("improveTheSourceCode", New("TextAction", [Str("Improve the source code.")])),
      Var("readTheSourceCode", New("TextAction", [Str("Read the source code.")])),
      Var("readTheInstantMessengerNames", New("TextAction", [Str("Look at the names in the instant messenger.")])),
      Var("openGoogle", New("TextAction", [Str("Open google.com in a web browser.")])),
      Var("openCompanyWiki", New("TextAction", [Str("Open the company wiki in a web browser.")])),
      Var("runGitLog", New("TextAction", [Str("Run `git log <filename>`.")])),

      #You can make x work if you can find a knowledgeable entity and ask the knowledgeable entity for help
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("xWorks"), Get("didYouFindHelp"), Get("askForHelp")])]),
      #You can make X work if you you understand the problem and simply fix it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("xWorks"), Get("doYouUnderstandTheProblem"), Get("justSolveIt")])]),

      #You can understand the problem if you read some helpful logs
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheProblem"), Get("didYouFindHelpfulLogs"), Get("readTheLogs")])]),
      #You can understand the problem if I analyze some logs
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheProblem"), Get("canYouFindAnyLogs"), Get("haveMeAnalyzeTheLogs")])]),
      #You can understand the problem if you diff with a version that works
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheProblem"), Get("canYouFindAVersionThatWorks"), Get("diffThem")])]),
      #You can understand the problem if you wait until you feel better
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheProblem"), Get("canYouAffordToWait"), Get("waitUntilYouFeelRefreshed")])]), #I can also include some jokes for making the user feel refreshed
      
      #You can understand the problem if you wait until it happens again
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheProblem"), Get("canYouAffordToWait"), Get("waitUntilItHappensAgain")])]),

      #You can have clear logs if you have good source code and rerun the program
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("didYouFindHelpfulLogs"), Get("doYouHaveGoodSourceCode"), Get("rerunTheProgram")])]),

      #You can have good source code if you understand the source code and you improve the source code
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouHaveGoodSourceCode"), Get("doYouUnderstandTheSourceCode"), Get("improveTheSourceCode")])]),

      #You can understand the source code if have the source code and you read it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("doYouUnderstandTheSourceCode"), Get("doYouHaveAnySourceCode"), Get("readTheSourceCode")])]),

      #You can find a knowledgeable entity if you have an instant messenger and look at the names inside it
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("didYouFindHelp"), Get("doYouHaveAnInstantMessenger"), Get("readTheInstantMessengerNames")])]),
      #You can find a knowledgeable entity if you have internet and you open google.com
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("didYouFindHelp"), Get("doYouHaveInternet"), Get("openGoogle")])]),
      #You can find a knowledgeable entity if you have internet and you open the company wiki
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("didYouFindHelp"), Get("doYouHaveInternet"), Get("openCompanyWiki")])]),
      #You can find a knowledgeable entity if you have source code and run 'git log'
      DotCall(Get("solver"), "addSolution", [New("Solution", [Get("didYouFindHelp"), Get("doYouHaveAnySourceCode"), Get("runGitLog")])]),

      Return(Get("solver")),

      Var("solutionA", New("Solution", [Get("didYouFindHelp"), Get("doYouHaveAnySourceCode"), Get("runGitLog")])),
    ]),


    Var("solver", Call("makeSolver")),

    #a query given to the user that the user is encouraged to respond to
    Class("Question")
      .vars({"communicator":"Communicator"})
      .func(Sig("answer", ["responseText"]), [
        #called when the user gives a response
        AbstractException()
      ])
      .func(Sig("getQueryText", []), [
        #the text to show to the user in order to ask this question
        AbstractException()
      ])
      .func(Sig("toString"), [
        Return(SelfCall("getQueryText"))
      ])
      .func(Sig("isSatisfied", []), [
        AbstractException()
      ])
      .func(Sig("recognizesAnswer", ["responseText"]), [
        Return(Bool(True)),
      ]),

    #a query given to the user that consists of several related questions
    Class("CompositeQuestion")
      .inherit("Question")
      .vars({"questions":"List"})
      .init([], [
        SelfSet("questions", New("List")),
      ])
      .func(Sig("addQuestion", ["question"]), [
        DotCall(SelfGet("questions"), "append", [Get("question")]),
      ])
      .func(Sig("clear"), [
        DotCall(SelfGet("questions"), "clear"),
      ])
      .func(Sig("getNextQuestion", []), [
        Return(DotCall(SelfGet("questions"), "tryGet", [Num(0)])),
      ])
      .func(Sig("removeQuestion", []), [
        DotCall(SelfGet("questions"), "removeAt", [Num(0)]),
      ])
      .func(Sig("getQueryText", []), [
        If(Not(SelfCall("isSatisfied"))).then([
          Return(DotCall(SelfCall("getNextQuestion"), "getQueryText"))
        ]).otherwise([
          Return(Str(None))
        ])
      ])
      .func(Sig("isSatisfied", []), [
        Return(IsNone(SelfCall("getNextQuestion"))),
      ])
      .func(Sig("answer", ["text"]), [
        DotCall(SelfCall("getNextQuestion"), "answer", [Get("text")]),
        If(DotCall(SelfCall("getNextQuestion"), "isSatisfied")).then([
          SelfCall("removeQuestion"),
        ]),
        If(SelfCall("isSatisfied")).then([
          SelfCall("done")
        ]),
      ])
      .func(Sig("recognizesAnswer", ["text"]), [
        Var("nextQuestion", SelfCall("getNextQuestion")),
        If(IsNone(Get("nextQuestion"))).then([
          Return(Bool(False)),
        ])
        .otherwise([
          Return(DotCall(Get("nextQuestion"), "recognizesAnswer", [Get("text")])),
        ]),
      ])
      .func(Sig("done", []), [
      ]),


    #text question that holds a text response
    Class("TextQuestion")
      .inherit("Question")
      .vars({"queryText":"String", "responseText":"String", "satisfied":"Bool"})
      .init(["queryText"], [
        SelfSet("satisfied", Bool(False)),
      ])
      .func(Sig("getQueryText", []), [
        Return(SelfGet("queryText")),
      ])
      .func(Sig("isSatisfied", []), [
        Return(SelfGet("satisfied")),
      ])
      .func(Sig("answer", ["responseText"]), [
        SelfSet("responseText", Get("responseText")),
        SelfSet("satisfied", Bool(True)),
        SelfCall("done")
      ])
      .func(Sig("done", []), [
      ]),

    #a request from the Communicator to the user to describe a fact to give to the Solver
    Class("FactQuery")
      .inherit("CompositeQuestion")
      .vars({"keyPrompt":"TextQuestion",
          "valuePrompt":"TextQuestion"})
      .init([], [
        SuperCall("__init__"),
        SelfSet("keyPrompt", New("TextQuestion", [Str("Fact name:")])),
        SelfSet("valuePrompt", New("TextQuestion", [Str("Fact value:")])),
        SelfCall("addQuestion", [SelfGet("keyPrompt")]),
        SelfCall("addQuestion", [SelfGet("valuePrompt")]),
      ])
      .func(Sig("done", []), [
        DotCall(SelfGet("communicator"), "enterTextFact", [
            DotGet(SelfGet("keyPrompt"), "responseText"),
            DotGet(SelfGet("valuePrompt"), "responseText")
            ]),
      ]),

    Class("UsernameQuery")
      .inherit("TextQuestion")
      .init([], [
        SuperCall("__init__", [Str("username: ")]),
      ])
      .func(Sig("done", []), [
        DotCall(SelfGet("communicator"), "setUsername", [SelfGet("responseText")]),
      ]),

    Class("MultipleChoiceQuestion")
      .inherit("Question")
      .vars({"choices":"List<String>",
             "satisfied":"Bool",
             "header":"String"})
      .init([], [
        SelfSet("satisfied", Bool(False)),
        SelfSet("choices", New("List")),
        SelfSet("header", Str("")),
      ])
      .func(Sig("addChoice", ["choice"]), [
        DotCall(SelfGet("choices"), "append", [Get("choice")]),
      ])
      .func(Sig("addChoices", ["choices"]), [
        ForEach("choice", Get("choices"), [
          SelfCall("addChoice", [Get("choice")]),
        ]),
      ])
      .func(Sig("getChoice", ["indexText"]), [
        Var("intChoice", Int(Get("indexText"))),
        Var("result", Bool(False)),
        If(Not(IsNone(Get("intChoice")))).then([
          Set("result", DotCall(SelfGet("choices"), "tryGet", [Get("intChoice")])),
        ]),
        Return(Get("result")),
      ])
      .func(Sig("recognizesAnswer", ["choice"]), [
        Return(Not(IsNone(SelfCall("getChoice", [Get("choice")])))),
      ])
      .func(Sig("answer", ["responseText"]), [
        SelfSet("satisfied", Bool(True)),
        SelfCall("choseChoice", [SelfCall("getChoice", [Get("responseText")])]),
      ])
      .func(Sig("choseChoice", ["choiceText"]), [
        AbstractException(),  
      ])
      .func(Sig("getQueryText", []), [
        Var("length", DotCall(SelfGet("choices"), "getLength")),
        Var("result", Concat([SelfGet("header"), Str("\nChoose one of these "), DotCall(Get("length"), "toString"), Str(" choices\n")])),
        For("i", Num(0), Get("length"), [
          Var("choice", DotCall(SelfGet("choices"), "get", [Get("i")])),
          Set("result", Concat([Get("result"), DotCall(Get("i"), "toString"), Str(": "), DotCall(Get("choice"), "toString"), Str("\n")])),
        ]),
        Return(Get("result")),
      ])
      .func(Sig("isSatisfied", []), [
        Return(SelfGet("satisfied")),
      ]),
 
    Class("SolveProblem_Query")
      .inherit("MultipleChoiceQuestion")
      .init([], [
        SuperCall("__init__"),
        SelfSet("header", Str("These are the problems I can solve!\n")),
      ])
      .func(Sig("choseChoice", ["choiceText"]), [
        DotCall(SelfGet("communicator"), "solveProblem", [Get("choiceText")]),
      ]),

    Class("AcceptOrReject_Query")
      .inherit("MultipleChoiceQuestion")
      .vars({"acceptText":"String", "rejectText":"String", "solutions":"List<Solution>"})
      .init(["solutions"], [
        SuperCall("__init__"),
        SelfSet("header", Str("Please choose whether to accept (execute) or to reject (mark as not feasible) one of these solutions\n")),

        SelfSet("acceptText", Str("Accept")),
        SelfCall("addChoice", [SelfGet("acceptText")]),

        SelfSet("rejectText", Str("Reject")),
        SelfCall("addChoice", [SelfGet("rejectText")]),
      ])
      .func(Sig("choseChoice", ["choiceText"]), [
        DotCall(SelfGet("communicator"), "respondToSolutionAction", [SelfGet("solutions"), Get("choiceText")]),
      ]),

    Class("SelectSolution_Query")
      .inherit("MultipleChoiceQuestion")
      .vars({"action":"String"})
      .init(["solutions", "action"], [
         SuperCall("__init__"),
         SelfCall("addChoices", [Get("solutions")]),
      ])
      .func(Sig("choseChoice", ["choice"]), [
        DotCall(SelfGet("communicator"), "respondToSolutionSelection", [SelfGet("action"), Get("choice")]),
      ]),
      
             
    #talks to the user, answers "why", forwards requests onto the Solver
    Class("Communicator")
      .vars({"universe": "Universe",
        "question":"CompositeQuestion",
        "username":"String"})
      .init([], [
        SelfSet("universe", New("Universe")),
        SelfSet("question", New("CompositeQuestion")),
        SelfCall("setUsername", [Str("jeff")]),
      ])
      .func(Sig("showGenericHelp", []), [
        Print(Str("""
        help   <keyword> - Ask me for usage of keyword <keyword> .
        solve            - Ask me to ask you what you would like solved.
        y      <id>      - Ask me how I deduced statement number <id> .
        clear            - Ask me to output lots of blank lines
        nvm              - Ask me to cancel the question that I'm asking
        """))
      ])
      .func(Sig("showJustificationHelp", []), [
         Print(Str("\nSome of my statements will have numbers in parentheses to the left, like this:")),
         PrintWithId(Str("Tada!")),
         Print(Str("\nThe format of this output is:")),
         Print(Str("- (#<whyId>): <text>")),
         Print(Str("\nType 'y <whyId>' to list statements that support statement number <whyId>")),
         Print(Str("")),
         Print(Str("The result wil be some output that looks like this:\n")),
         ShortExplain(Str("Tadaa!"), Const(1)),
         Print(Str("")),
         Print(Str("The format of each of these lines is:\n")),
         Print(Str("- (#<whyId>) [lines <lineA>/<lineB>]: <text>\n")),
         Print(Str("See line number <lineA> in my source code for the corresponding low-level implementation")),
         Print(Str("See line number <lineB> in my source code for the corresponding high-level implementation")),
         Print(Str("Type 'y <whyId>' for these statements too to list statements that support them\n")),
      ])
      .func(Sig("showSolveHelp", []), [
         Print(Str("""
         Type 'solve' and I will ask you what problem you would like to have solved
         """))
      ])
      .func(Sig("showClearHelp", []), [
         Print(Str("""
         Type 'clear' and I will output lots of blank lines
         """))
      ])
      .func(Sig("showNevermindHelp", []), [
         Print(Str("""
         Type 'nvm' and I will cancel my current question
         If I have a current question, then I repeat the question everytime I show the prompt
         """))
      ])
      .func(Sig("showSarcasticHelpHelp", []), [
         Print(Str("""
         Really? You're asking for help with the 'help' keyword? Ok. Here goes:
         """)),
         SelfCall("showHelpHelp"),
      ])
      .func(Sig("showHelpHelp", []), [
         Print(Str("""
         help           - Ask me for a list of statements and brief usage instructions for each
         help <keyword> - Ask me for usage of keyword <keyword>
         """)),
      ])
      .func(Sig("enterTextFact", ["key", "value"]), [
        DotCall(SelfGet("universe"), "putProp", [Get("key"), DotCall(Str("True"), "equals", [Get("value")])]),
      ])
      .func(Sig("setQuestion", ["question"]), [
        DotCall(SelfGet("question"), "clear"),
        DotCall(SelfGet("question"), "addQuestion", [Get("question")]),
      ])
      .func(Sig("setUsername", ["username"]), [
        Print(Str("")),
        #Print(Concat([Str("Hi, "), Get("username")])),
        #Print(Str("Hi")),
        SelfSet("username", Get("username")),
      ])
      .func(Sig("respondToClear"), [
        Print(Str("\n" * 10)),
      ])
      .func(Sig("respondToNevermind"), [
        DotCall(SelfGet("question"), "clear"),
      ])
      .func(Sig("respondToSolutionAction", ["solutions", "choiceText"]), [
        If(Not(DotCall(Str("Cancel"), "equals", [Get("choiceText")]))).then([
          If(DotCall(DotCall(Get("solutions"), "getLength"), "equals", [Num(1)])).then([
            Var("s1", DotCall(Get("solutions"), "get", [Num(0)])),
            SelfCall("respondToSolutionSelection", [Get("choiceText") , Get("s1")]),
          ]).otherwise([
            Var("question", New("SelectSolution_Query", [Get("solutions"), Get("choiceText")])),
            DotSet(Get("question"), "communicator", Get("self")),
            SelfCall("setQuestion", [Get("question")]),
          ])
        ]),
      ])
      .func(Sig("respondToSolutionSelection", ["acceptOrReject", "solution"]), [
        If(DotCall(Str("Accept"), "equals", [Get("acceptOrReject")])).then([
          DotCall(Get("solution"), "execute"),
        ]).otherwise([
          Var("rejected", DotCall(DotGet(Get("solution"), "prerequisite"), "toString")),
          Print(Concat([Str("Marking as infeasible '"), Get("rejected"), Str("'")])),
          SelfCall("enterTextFact", [Get("rejected"), Str("False")]),
        ])
      ])
      .func(Sig("respondToHelp", ["text"]), [
        Var("keyword", Get("text")),
        If(DotCall(Str("help"), "equals", [Get("keyword")])).then([
          SelfCall("showSarcasticHelpHelp")
        ]).otherwise([
          If(DotCall(Str("solve"), "equals", [Get("keyword")])).then([
            SelfCall("showSolveHelp")
          ]).otherwise([
            If(DotCall(Str("y"), "equals", [Get("keyword")])).then([
              SelfCall("showJustificationHelp")
            ]).otherwise([
              If(DotCall(Str("clear"), "equals", [Get("keyword")])).then([
                SelfCall("showClearHelp")
              ]).otherwise([
                If(DotCall(Str("nvm"), "equals", [Get("keyword")])).then([
                  SelfCall("showNevermindHelp")
                ]).otherwise([
                  If(DotCall(Str(""), "equals", [Get("keyword")])).then([
                    Print(Str("""Here is what I can understand:"""))
                  ]).otherwise([
                    Print(Str("""Sorry; I don't recognize that keyword. Here is what I can understand:"""))
                  ]),
                  SelfCall("showGenericHelp"),
                ]),
              ])
            ])
          ])
        ])
      ])
      .func(Sig("respondToWhy", ["idText"]), [
        #say why
        Var("justificationId", Int(Get("idText"))),
        If(DotCall(Get("justificationId"), "nonEmpty")).then([
          ShortExplain(JustificationGetter(Get("justificationId")), Const(1)),
          Print(Str("")),
        ]).otherwise([
          SelfCall("showJustificationHelp")
        ]),
      ])
      .func(Sig("respondToSolve", []), [
        Var("question", New("SolveProblem_Query")),
        DotSet(Get("question"), "communicator", Get("self")),
        ForEach("problemText", DotGet(SelfGet("solver"), "solutions"), [
          DotCall(Get("question"), "addChoice", [Get("problemText")]),
        ]),
        SelfCall("setQuestion", [Get("question")]),
      ])
      .func(Sig("solveProblem", ["queryText"]), [
        #help solve the user's external problem
        Var("problem1", New("TextProposition", [Get("queryText")])),
        Var("universe", SelfGet("universe")),
        Var("solutions", DotCall(Get("solver"), "trySolve", [Get("problem1"), Get("universe")])),
        Var("numSolutions", DotCall(Get("solutions"), "getLength")),
        Print(Concat([DotCall(Get("numSolutions"), "toString"), Str(" possible solutions found:")])),
        If(DotCall(Num(0), "equals", [Get("numSolutions")])).then([
          Print(Str("Sorry, I don't have any more solutions to that problem.")),
        ]).otherwise([
          Print(Str("")),
          Var("question", New("AcceptOrReject_Query", [Get("solutions")])),
          DotSet(Get("question"), "communicator", Get("self")),
          ForEach("solution", Get("solutions"), [
            DotCall(Get("solution"), "offer"),
            #Print(Str("")),
          ]),
          Print(Str("")),
          SelfCall("setQuestion", [Get("question")]),
        ])
      ])
      .func(Sig("respondToAnswer", ["answerText"]), [
        If(DotCall(SelfGet("question"), "isSatisfied")).then([
          Print(Str("I didn't ask you a question!")),
        ]).otherwise([
          DotCall(SelfGet("question"), "answer", [Get("answerText")]),
        ]),
      ])
      .func(Sig("respondToFactEntry", []), [
        Print(Str("All right! What fact would you like to tell me?")),
        
        Var("question", New("FactQuery")),
        DotSet(Get("question"), "communicator", Get("self")),
        SelfCall("setQuestion", [Get("question")]),
      ])
      .func(Sig("respond", ["responseText"]), [
        Print(Str("")),

        Var("components", DotCall(Get("responseText"), "split", [Str(" ")])),
        Var("component0", DotCall(Get("components"), "get", [Num(0)])),
        Var("argumentText", DotCall(Get("responseText"), "exceptPrefix", [Get("component0")])),
        Set("argumentText", DotCall(Get("argumentText"), "exceptPrefix", [Str(" ")])),

        If(DotCall(Str("y"), "equals", [Get("component0")])).then([
          SelfCall("respondToWhy", [Get("argumentText")])
        ]).otherwise([
         If(DotCall(Str("solve"), "equals", [Get("component0")])).then([
            SelfCall("respondToSolve")
          ]).otherwise([
            If(DotCall(Str("help"), "equals", [Get("component0")])).then([
              SelfCall("respondToHelp", [Get("argumentText")]),
            ]).otherwise([
              If(DotCall(Str("clear"), "equals", [Get("responseText")])).then([
                SelfCall("respondToClear"),
              ]).otherwise([
                If(DotCall(Str("nvm"), "equals", [Get("responseText")])).then([
                  SelfCall("respondToNevermind"),
                ]).otherwise([
                  If(DotCall(SelfGet("question"), "recognizesAnswer", [Get("responseText")])).then([
                    DotCall(SelfGet("question"), "answer", [Get("responseText")]),
                  ]).otherwise([
                    Print(Str("""Sorry; I'm a robot, and English is only my second language. Type 'help' for help.""")),
                  ])
                ])
              ])
            ])
          ])
        ])
      ])
      .func(Sig("talkOnce", []), [
        Var("standardPrompt", Str("Say something! ")),
        Var("prompt", Const(None)),
        If(DotCall(SelfGet("question"), "isSatisfied")).then([
          Set("prompt", Get("standardPrompt")),
        ]).otherwise([
          Set("prompt", Concat([DotCall(SelfGet("question"), "getQueryText"),
            Str("\nAlternatively, enter any standard menu option including 'help' for help.\n"),
            Get("standardPrompt")])),
        ]),
        #PrintWithId(Get("prompt")),
        Var("response", Ask(WithId(Get("prompt")))),
        DotCall(Get("self"), "respond", [Get("response")]),
      ])
      .func(Sig("communicate", []), [
        Print(Str("")),
        While(Bool(True), [
          SelfCall("talkOnce"),
        ]),
      ]),

    Var("communicator", New("Communicator")),
    DotCall(Get("communicator"), "communicate"),
  ])
  execution = Execution(program)
  execution.run()

def inheritanceTest():
  program = Program()
  program.put([
    Class("TestGrandParent")
      .init([], [
        Print(Str("running init in TestGrandParent class"))
      ])
      .func(Sig("talk", []), [
        Print(Str("running talk in TestGrandParent class")),
      ]),
    Class("TestParent")
      .inherit("TestGrandParent")
      .init([], [
        Print(Str("running init in TestParent class")),
        SuperCall("__init__"),
        SelfCall("talk")
      ])
      .func(Sig("talk", []), [
        Print(Str("running talk in TestParent class")),
        SuperCall("talk"),
      ]),
    Class("TestChild")
      .inherit("TestParent")
      .init([], [
        Print(Str("running init in TestChild class")),
        SuperCall("__init__"),
      ])
      .func(Sig("talk", []), [
        Print(Str("running talk in TestChild class")),
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

    Var("a", New("ArgTester", [Str("abcd")])),
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
