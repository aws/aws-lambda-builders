

# TODO: Is this datastructure threadsafe?
# Maintains a registry of builders
_REGISTRY = {}


def get_builder(language, language_framework, application_framework):
    """
    Find and return a builder class capable of building for the given combination of capabilities

    :param language:
    :param language_framework:
    :param application_framework:

    :return:
    :raises BuilderNotFoundError: If a builder was not registered
    """
    pass


class WorkflowMetaClass(type):
    """
    A metaclass that maintains the registry of loaded builders
    """

    def __new__(mcs, name, bases, class_dict):
        """
        Add the builder to registry when loading the class
        """

        cls = type.__new__(mcs, name, bases, class_dict)

        return cls


