test-basic
==========

.. system:process:: ParentOfP1P2
    :become_parent:

.. system:process:: P1
    :consumes: Apples Blackberries
    :produces: Crumble
    :label: Making crumble

.. system:process:: P2
    :consumes: Blackberries
    :produces: BlackberryFool
    :label: Making blackberry fool

.. end-sub-processes::

.. system:process:: AnotherParentOfP1P2
    :composed_of: *ParentOfP1P2

    TODO: This does not show up as a parent currently because it's only added
    later.
