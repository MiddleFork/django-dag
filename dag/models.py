"""
A class to model hierarchies of objects following
Directed Acyclic Graph structure.

Some ideas stolen from: from https://github.com/stdbrouw/django-treebeard-dag

"""


from django.db import models
from django.core.exceptions import ValidationError


class NodeNotReachableException (Exception):
    """
    Exception for vertex distance and path
    """
    pass


class NodeBase(object):
    """
    Main node abstract model
    """

    class Meta:
        ordering = ('-id',)

    def __unicode__(self):
        return "# %s" % self.pk

    def __str__(self):
        return self.__unicode__()

    def add_child(self, descendant, **kwargs):
        """
        Adds a parent
        """
        args = kwargs
        args.update({'parent' : self, 'child' : descendant })
        cls = self.children.through(**kwargs)
        return cls.save()


    def add_parent(self, parent, *args, **kwargs):
        """
        Adds a parent
        """
        return parent.add_child(self, **kwargs)

    def parents(self):
        """
        Returns all elements which have 'self' as a direct descendant
        """
        return self.__class__.objects.filter(children = self)

    def descendants_tree(self):
        """
        Returns a tree-like structure with progeny
        """
        tree = {}
        for f in self.children.all():
            tree[f] = f.descendants_tree()
        return tree

    def ancestors_tree(self):
        """
        Returns a tree-like structure with ancestors
        """
        tree = {}
        for f in self.parents():
            tree[f] = f.ancestors_tree()
        return tree

    def descendants_set(self):
        """
        Returns a set of descendants
        """
        res = set()
        for f in self.children.all():
            res.add(f)
            res.update(f.descendants_set())
        return res

    def ancestors_set(self):
        """
        Returns a set of ancestors
        """
        res = set()
        for f in self.parents():
            res.add(f)
            res.update(f.ancestors_set())
        return res

    def distance(self, target):
        """
        Returns the shortest hops count to the target vertex
        """
        return len(self.path(target))

    def path(self, target):
        """
        Returns the shortest path
        """
        if self == target:
            return []
        if target in self.children.all():
            return [target]
        if target in self.descendants_set():
            path = None
            for d in self.children.all():
                try:
                    desc_path = d.path(target)
                    if not path or len(desc_path) < path:
                        path = [d] + desc_path
                except NodeNotReachableException:
                    pass
        else:
            raise NodeNotReachableException
        return path



    @staticmethod
    def circular_checker(parent, child):
        """
        Checks that the object is not an ancestor or a descendant
        """
        if child in parent.ancestors_set():
            raise ValidationError('The object is an ancestor.')
        if child in parent.descendants_set():
            raise ValidationError('The object is a descendant.')



def edge_factory(node_model, child_to_field="id", parent_to_field="id", concrete=True):
    """
    Dag Edge
    """
    class Edge(models.Model):
        class Meta:
            abstract = not concrete

        parent = models.ForeignKey(node_model, related_name="%s_child" % node_model, to_field=parent_to_field)
        child = models.ForeignKey(node_model, related_name="%s_parent" % node_model, to_field=child_to_field)

        def __unicode__(self):
            return "%s is child of %s" % (self.child, self.parent)

        def save(self, *args, **kwargs):
            self.parent.__class__.circular_checker(self.parent, self.child)
            super(Edge, self).save(*args, **kwargs) # Call the "real" save() method.

    return Edge


"""
Django's ORM is somewhat magical. We can't monkeypatch AL_Node
(e.g. do stuff like AL_Node.parents = models.ManyToManyField(...))
so we have put all functionality in a base class, and use a factory
to fill in the details of the Node model.
"""

def node_factory(edge_model_name, children_null = True):
    class Node(models.Model, NodeBase):
        class Meta:
            abstract = True

        children  = models.ManyToManyField(
                'self',
                null        = children_null,
                blank       = children_null,
                symmetrical = False,
                through     = edge_model_name)

        parent_field        = '%s_parent' % edge_model_name.lower()
        child_field         = '%s_child' % edge_model_name.lower()

    return Node
