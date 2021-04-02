test-basic
==========

.. system:process:: P1
    :consumes: Apples Blackberries
    :produces: Crumble
    :label: Making crumble

.. system:process:: P2
    :consumes: Blackberries
    :produces: BlackberryFool
    :label: Making blackberry fool

.. system:process:: ParentOfP1P2
    :composed_of: P1 P2

.. system:process:: AnotherParentOfP1P2
    :composed_of: *ParentOfP1P2

.. system:process:: ErrorMissingProcess
    :composed_of: *Missing
