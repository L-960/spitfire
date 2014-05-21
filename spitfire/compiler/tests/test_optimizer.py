import unittest
from spitfire.compiler.ast import *
from spitfire.compiler import analyzer
from spitfire.compiler import util
from spitfire.compiler import optimizer


class BaseTest(unittest.TestCase):

  def __init__(self, *args):
    unittest.TestCase.__init__(self, *args)
    self.options = analyzer.default_options

  def setUp(self):
    self.compiler = util.Compiler(
        analyzer_options=self.options,
        xspt_mode=False)

  def _get_analyzer(self, ast_root):
    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)
    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)
    return optimization_analyzer

  def _build_function_template(self):
    """ Build a simple template with a function.

    file: TestTemplate
    #def test_function
    #end def
    """
    ast_root = TemplateNode('TestTemplate')
    function_node = FunctionNode('test_function')
    ast_root.append(function_node)
    return (ast_root, function_node)

  def _build_if_template(self, condition=None):
    """ Build a simple template with a function and an if statement.

    file: TestTemplate
    #def test_function
      #if True
      #end if
    #end def
    """
    ast_root, function_node = self._build_function_template()
    condition_node = condition or LiteralNode(True)
    if_node = IfNode(condition_node)
    function_node.append(if_node)
    return (ast_root, function_node, if_node)



class TestAnalyzeListLiteralNode(BaseTest):

  def test_list_elements_are_optimized(self):
    self.ast_description = """
    Input:
    [1, 2, 3]
    """
    ast_root = ListLiteralNode('list')
    ast_root.child_nodes.append(LiteralNode(1))
    ast_root.child_nodes.append(LiteralNode(2))
    ast_root.child_nodes.append(LiteralNode(3))

    optimization_analyzer = self._get_analyzer(ast_root)
    optimization_analyzer.visit_ast(ast_root)
    self.assertEqual(len(optimization_analyzer.visit_ast.GetCalls()), 4)


class TestAssignAfterFilterWarning(unittest.TestCase):

  def setUp(self):
    options = analyzer.default_options
    options.update(cache_resolved_placeholders=True,
                   enable_warnings=True, warnings_as_errors=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def assign_after_filter_fails(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #set $foo = 'foo'
      $foo
      #set $foo = 'bar'
      $foo
    #end def
    """
    ast_root, function_node = self._build_function_template()
    first_assign = AssignNode(IdentifierNode('foo'), LiteralNode('foo'))
    function_node.append(first_assign)
    first_use = FilterNode(IdentifierNode('foo'))
    function_node.append(first_use)
    second_assign = AssignNode(IdentifierNode('foo'), LiteralNode('bar'))
    function_node.append(second_assign)
    second_use = FilterNode(IdentifierNode('foo'))
    function_node.append(second_use)

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    self.assertRaises(util.Warning,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def double_assign_ok(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #set $foo = 'foo'
      #set $foo = 'bar'
      $foo
    #end def
    """
    ast_root, function_node = self._build_function_template()
    first_assign = AssignNode(IdentifierNode('foo'), LiteralNode('foo'))
    function_node.append(first_assign)
    second_assign = AssignNode(IdentifierNode('foo'), LiteralNode('bar'))
    function_node.append(second_assign)
    first_use = FilterNode(IdentifierNode('foo'))
    function_node.append(first_use)

    optimization_analyzer = optimizer.OptimizationAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    optimization_analyzer.visit_ast = unittest.RecordedFunction(
        optimization_analyzer.visit_ast)

    try:
      optimization_analyzer.visit_ast(ast_root)
    except util.Warning:
      self.fail('visit_ast raised WarningError unexpectedly.')


class TestPartialLocalIdentifiers(BaseTest):

  def setUp(self):
    # TODO: Use BaseTest.setUp()?
    options = analyzer.default_options
    options.update(static_analysis=True,
                   directly_access_defined_variables=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def test_simple_if(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    assign_node = AssignNode(IdentifierNode('foo'), LiteralNode(1))
    if_node.append(assign_node)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_if_partial_else(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #else
        #set $bar = 1
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(1)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_partial_if_else(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #else
        #set $bar = 1
      #end if
      $bar
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(1)))
    function_node.append(PlaceholderNode('bar'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_nested_else(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #elif
        #set $foo = 2
      #else
        #set $foo = 3
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    if_node.else_.append(if_node_2)

    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)

    try:
      optimization_analyzer.visit_ast(ast_root)
    except analyzer.SemanticAnalyzerError:
      self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

  def test_nested_if(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #if True
          #set $foo = 1
        #else
          #set $foo = 2
        #end if
      #else
        #set $foo = 3
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node.append(if_node_2)
    if_node.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)

    try:
      optimization_analyzer.visit_ast(ast_root)
    except analyzer.SemanticAnalyzerError:
      self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

  def test_partial_nested_if(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #if True
          #set $foo = 1
        #else
          #set $bar = 2
        #end if
      #else
        #set $foo = 3
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2.else_.append(AssignNode(IdentifierNode('bar'), LiteralNode(2)))
    if_node.append(if_node_2)
    if_node.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_partial_nested_else(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #else
        #if
          #set $bar = 2
        #else
          #set $baz = 3
        #end if
      #end if
      $baz
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('bar'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('baz'), LiteralNode(3)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('baz'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_partial_nested_else_if(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #else
        #if True
          #set $foo = 2
        #end if
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)

  def test_nested_else(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #else
        #if
          #set $foo = 2
        #else
          #set $foo = 3
        #end if
      #end if
      $foo
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(AssignNode(IdentifierNode('foo'), LiteralNode(2)))
    if_node_2.else_.append(AssignNode(IdentifierNode('foo'), LiteralNode(3)))
    if_node.else_.append(if_node_2)
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer(ast_root)

    try:
      optimization_analyzer.visit_ast(ast_root)
    except analyzer.SemanticAnalyzerError:
      self.fail('visit_ast raised SemanticAnalyzerError unexpectedly.')

  def test_nested_partial_use(self):
    self.ast_description = """
    file: TestTemplate
    #def test_function
      #if True
        #set $foo = 1
      #end if
      #if True
        $foo
      #end if
    #end def
    """
    ast_root, function_node, if_node = self._build_if_template()
    if_node.append(AssignNode(IdentifierNode('foo'), LiteralNode(1)))
    if_node_2 = IfNode(LiteralNode(True))
    if_node_2.append(PlaceholderNode('foo'))
    function_node.append(if_node_2)

    optimization_analyzer = self._get_analyzer(ast_root)
    self.assertRaises(analyzer.SemanticAnalyzerError,
                      optimization_analyzer.visit_ast,
                      ast_root)


class TestFinalPassHoistConditional(BaseTest):

  def setUp(self):
    options = analyzer.default_options
    options.update(static_analysis=True,
                   directly_access_defined_variables=True,
                   hoist_conditional_aliases=True,
                   cache_filtered_placeholders=True)
    self.compiler = util.Compiler(
        analyzer_options=options,
        xspt_mode=False,
        compiler_stack_traces=True)

  def test_hoist_both(self):
    self.ast_description = """
    file: TestTemplate
    #global $foo
    #def test_function
      #if True
        $foo
      #else
        $foo
      #end if
    #end def
    """

    def scope_setter(scope):
      scope.local_identifiers.add(IdentifierNode('_rph_foo'))
      scope.aliased_expression_map[PlaceholderNode('foo')] = (
          IdentifierNode('_rph_foo'))
      scope.aliased_expression_map[FilterNode(IdentifierNode('_rph_foo'))] = (
          IdentifierNode('_fph123'))
      scope.alias_name_set.add('_fph123')
      scope.alias_name_set.add('_rph_foo')

    def build_conditional_body(node):
      node.append(
          AssignNode(
              IdentifierNode('_rph_foo'),
              PlaceholderNode('foo')))
      node.append(
          AssignNode(
              IdentifierNode('_fph123'),
              FilterNode(IdentifierNode('_rph_foo'))))
      node.append(
          BufferWrite(IdentifierNode('_fph123')))

    ast_root, function_node, if_node = self._build_if_template()
    ast_root.global_placeholders.add('foo')
    scope_setter(function_node.scope)
    function_node.scope.local_identifiers.add(IdentifierNode('self'))
    scope_setter(if_node.scope)
    scope_setter(if_node.else_.scope)
    build_conditional_body(if_node)
    build_conditional_body(if_node.else_)

    final_pass_analyzer = optimizer.FinalPassAnalyzer(
        ast_root,
        self.compiler.analyzer_options,
        self.compiler)

    final_pass_analyzer.hoist = unittest.RecordedFunction(
        final_pass_analyzer.hoist)

    final_pass_analyzer.visit_ast(ast_root)

    # The 4 calls are hoisting the rph alias and the fph alias out of
    # both the if and else clauses.
    self.assertEqual(len(final_pass_analyzer.hoist.GetCalls()), 4)


class TestHoistPlaceholders(BaseTest):

  def setUp(self):
      options = analyzer.default_options
      options.update(cache_resolved_placeholders=True,
                     enable_warnings=True, warnings_as_errors=True,
                     directly_access_defined_variables=True,
                     static_analysis=False)
      self.compiler = util.Compiler(
          analyzer_options=options,
          xspt_mode=False,
          compiler_stack_traces=True)

  def fake_placeholdernode_replacement(self, placeholder, local_var,
                                       cached_placeholder, local_identifiers):
    return self.options.cache_resolved_placeholders

  def _get_analyzer_and_visit(self, ast_root):
    analyzer = self._get_analyzer(ast_root)
    analyzer._placeholdernode_replacement = unittest.RecordedFunction(
        self.fake_placeholdernode_replacement)
    analyzer.visit_ast(ast_root)
    return analyzer

  def test_simple_hoist(self):
    self.ast_description = """
    file: TestTemplate

    #def test_function
      $foo
      $foo
    #end def
    """
    ast_root, function_node = self._build_function_template()
    function_node.append(PlaceholderNode('foo'))
    function_node.append(PlaceholderNode('foo'))

    optimization_analyzer = self._get_analyzer_and_visit(ast_root)
    self.assertEqual(
        optimization_analyzer._placeholdernode_replacement.GetResults(),
        [True, True])

  def test_hoists_both_from_plus(self):
    self.ast_description = """
    file: TestTemplate

    #global $foo

    #def test_function
      #set $bar = $foo + $foo
    #end def
    """
    ast_root, function_node = self._build_function_template()
    ast_root.global_placeholders.add('foo')
    function_node.append(
        AssignNode(IdentifierNode('bar'),
        BinOpNode('+', PlaceholderNode('foo'), PlaceholderNode('foo'))))

    optimization_analyzer = self._get_analyzer_and_visit(ast_root)
    self.assertEqual(
        optimization_analyzer._placeholdernode_replacement.GetResults(),
        [True, True])

  def test_hoists_lhs_only_from_and(self):
    self.ast_description = """
    file: TestTemplate

    #def test_function
      #if $foo or $bar
      #end if
    #end def
    """
    condition = BinOpNode('or',
                          PlaceholderNode('foo'),
                          PlaceholderNode('bar'))
    ast_root, function_node, if_node = self._build_if_template(condition)

    optimization_analyzer = self._get_analyzer_and_visit(ast_root)
    self.assertEqual(
        optimization_analyzer._placeholdernode_replacement.GetResults(),
        [True, False])


if __name__ == '__main__':
  unittest.main()