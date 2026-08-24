from typing import Callable, Optional, Any

# Centinela para detectar si se alcanzó el límite de profundidad
CUTOFF = "CUTOFF"

# Alias funciones modulares
type IsGoalFn[T] = Callable[[T], bool]
type GetSuccessorsFn[T] = Callable[[T], list[tuple[Any, T]]]

class Node[T]:
    def __init__(self, state: T, parent: Optional['Node[T]'] = None, action: Optional[Any] = None):
        self.state = state
        self.parent = parent
        self.action = action  # Acción que generó este estado

    def get_path(self) -> list['Node[T]']:
        """Reconstruye la secuencia de nodos desde la raíz."""
        node = self
        path = []

        while node:
            path.append(node)
            node = node.parent
        return path[::-1]

def dls[T](
    node: Node[T], 
    is_goal: IsGoalFn[T], 
    get_successors: GetSuccessorsFn[T], 
    depth: int
) -> Node[T] | str | None:
    """Depth-Limited Search con evaluación modular de objetivo y generación 'al vuelo'."""
    
    if is_goal(node.state):
        return node

    if depth == 0:
        return CUTOFF

    any_cutoff = False

    # Generación dinámica de sucesores (sin árbol en memoria)
    for action, successor_state in get_successors(node.state):
        child = Node(state=successor_state, parent=node, action=action)
        result = dls(child, is_goal, get_successors, depth - 1)

        if result == CUTOFF:
            any_cutoff = True

        elif result is not None:
            return result 
        
    return CUTOFF if any_cutoff else None


def iddfs[T](
    initial_state: T, 
    is_goal: IsGoalFn[T], 
    get_successors: GetSuccessorsFn[T], 
    max_depth: int = 24
) -> Optional[Node[T]]:
    """Iterative Deepening DFS con corte por agotamiento de espacio de estados."""
    
    for depth in range(max_depth + 1):
        root = Node(state=initial_state)
        result = dls(root, is_goal, get_successors, depth)

        if isinstance(result, Node):
            return result 
        
        if result is None:
            # El espacio de estados completo fue explorado sin encontrar solución
            return None

    return None  # Se alcanzó max_depth sin éxito

if __name__ == "__main__":
    pass