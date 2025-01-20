import torch
import torch.nn as nn

def get_vector_field(model: nn.Module, y: torch.Tensor) -> torch.Tensor:
    """
    Calculate the derivatives for the points in the phase space based on the trained HNN.

    Args:
        model (nn.Module): Trained Hamiltonian Neural Network (HNN).
        y (torch.Tensor): Current state, a tensor of shape (2) containing [q, p].

    Returns:
        torch.Tensor: Tensor of shape (2) containing [dq/dt, dp/dt].
    """
    y = y.detach().clone().requires_grad_(True)

    model.eval()
    H = model(y)

    grad_H = torch.autograd.grad(H, y, grad_outputs=torch.ones_like(H), create_graph=True)[0]

    # Extract predicted time derivatives using Hamilton's equations
    q_dot_pred = grad_H[1]  # ∂H/∂p
    p_dot_pred = -grad_H[0]  # -∂H/∂q

    return torch.stack([q_dot_pred, p_dot_pred])


def step(func, func_type: str ,y: torch.Tensor, h: float) -> torch.Tensor:
    """
    Perform a single step of the Leapfrog method.

    Args:
        func (Union[nn.Module, Callable]): Function or model that computes the time derivatives (vector field).
        func_type (str): Either "HNN", "FFNN" or "_" for vector_field
        y (torch.Tensor): Current state, a tensor of shape (2) containing [q, p].
        h (float): Step size.

    Returns:
        torch.Tensor: Updated state, a tensor of shape (2).
    """
    # Split state into position (q) and momentum (p)
    q = y[0:1]  # Position
    p = y[1:2]  # Momentum

    if func_type == "HNN":
        derivatives = get_vector_field(func, y)  # Get derivatives for current state from the trained model
    elif func_type == "FFNN":
        with torch.no_grad():
            derivatives = func(y) # Get derivatives for current state from the trained model
    else:
        derivatives = func(y)  # Get derivatives for current state from known vector field or FFNN prediction

    # Half-step momentum update
    p_half = p + 0.5 * h * derivatives[1:2]

    # Full-step position update
    q_next = q + h * p_half

    # Full-step momentum update
    y_next_half = torch.cat((q_next, p_half), dim=0)

    if func_type == "HNN":
        derivatives_next = get_vector_field(func, y_next_half)  # Get derivatives for current state from the trained model
    elif func_type == "FFNN":
        with torch.no_grad():
            derivatives_next = func(y)
    else:
        derivatives_next = func(y_next_half)  # Get derivatives for current state from known vector field
    p_next = p_half + 0.5 * h * derivatives_next[1:2]

    # Combine updated positions and momenta
    y_next = torch.cat((q_next, p_next), dim=0)
    return y_next


def solve(func, func_type: str, y0: torch.Tensor, t_span: tuple, h: float = 0.01) -> tuple:
    """
    Solve the system of ODEs using the Leapfrog method.

    Args:
        func (Union[nn.Module, Callable]): Function or model that computes the time derivatives (vector field).
        func_type (str): Either "HNN", "FFNN" or "_" for vector_field
        y0 (torch.Tensor): Initial state, a tensor of shape (2) containing [q, p].
        t_span (tuple): A tuple (t_start, t_end) defining the time interval.
        h (float, optional): Step size. Defaults to 0.01.

    Returns:
        tuple: A tuple containing:
            - t_values (torch.Tensor): Tensor of time points.
            - y_values (torch.Tensor): Tensor of state values at the corresponding time points.
    """
    t_start, t_end = t_span
    t = t_start
    y = y0.clone().detach()

    t_values = [t]
    y_values = [y.clone().detach()]

    while t < t_end:
        # Ensure we don't step past the end time
        if t + h > t_end:
            h = t_end - t

        # Perform a single Leapfrog step
        y = step(func, func_type, y, h)
        t += h

        # Store the results
        t_values.append(t)
        y_values.append(y.clone().detach())

    return torch.tensor(t_values, dtype=torch.float32), torch.stack(y_values)
