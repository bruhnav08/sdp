from django.core.exceptions import ValidationError
from django.db import transaction
from housekeeping.models import RoomStatusHistory
from room_inventory.models import Room


VALID_TRANSITIONS = {
    # target_status: set of allowed current statuses
    Room.Status.CLEANING_IN_PROGRESS: {Room.Status.VACANT_DIRTY, Room.Status.OCCUPIED, Room.Status.VACANT_CLEAN},
    Room.Status.VACANT_CLEAN: {Room.Status.CLEANING_IN_PROGRESS, Room.Status.VACANT_DIRTY, Room.Status.UNDER_MAINTENANCE, Room.Status.BLOCKED},
    Room.Status.VACANT_DIRTY: {Room.Status.VACANT_CLEAN, Room.Status.OCCUPIED, Room.Status.CLEANING_IN_PROGRESS, Room.Status.UNDER_MAINTENANCE, Room.Status.BLOCKED},
    Room.Status.UNDER_MAINTENANCE: {Room.Status.VACANT_CLEAN, Room.Status.VACANT_DIRTY, Room.Status.CLEANING_IN_PROGRESS, Room.Status.OCCUPIED, Room.Status.BLOCKED},
    Room.Status.OCCUPIED: {Room.Status.VACANT_CLEAN},
    Room.Status.BLOCKED: {Room.Status.VACANT_CLEAN, Room.Status.VACANT_DIRTY},
}


@transaction.atomic
def change_room_status(room: Room, new_status: str, user, remarks: str = "") -> RoomStatusHistory:
    """
    Validates transition, updates Room.status, and creates a RoomStatusHistory audit record.
    Raises ValidationError if transition is prohibited.
    """
    current_status = room.status

    if current_status == new_status:
        raise ValidationError(f"Room {room.room_number} is already in status '{dict(Room.Status.choices).get(new_status, new_status)}'.")

    # Specific guard: Cannot start cleaning if already cleaning in progress
    if current_status == Room.Status.CLEANING_IN_PROGRESS and new_status == Room.Status.CLEANING_IN_PROGRESS:
        raise ValidationError("Room is already being cleaned.")

    # General transition guard
    allowed = VALID_TRANSITIONS.get(new_status, set())
    if current_status not in allowed:
        raise ValidationError(
            f"Cannot transition Room {room.room_number} from '{dict(Room.Status.choices).get(current_status, current_status)}' to '{dict(Room.Status.choices).get(new_status, new_status)}'."
        )

    # Perform update
    room.status = new_status
    room.save(update_fields=["status", "updated_at"])

    # Log history audit record
    history = RoomStatusHistory.objects.create(
        room=room,
        previous_status=current_status,
        new_status=new_status,
        changed_by=user if user and user.is_authenticated else None,
        remarks=remarks or "",
    )

    return history


def get_available_actions(room: Room) -> list:
    """
    Returns list of valid next actions for a given room's current status.
    Each action item is dict with: 'target', 'label', 'btn_class'
    """
    s = room.status
    actions = []

    if s == Room.Status.VACANT_DIRTY:
        actions.append({"target": Room.Status.CLEANING_IN_PROGRESS, "label": "Start Cleaning", "btn_class": "warning"})
        actions.append({"target": Room.Status.VACANT_CLEAN, "label": "Mark Clean", "btn_class": "success"})
        actions.append({"target": Room.Status.UNDER_MAINTENANCE, "label": "Under Maintenance", "btn_class": "secondary"})

    elif s == Room.Status.CLEANING_IN_PROGRESS:
        actions.append({"target": Room.Status.VACANT_CLEAN, "label": "Mark Clean", "btn_class": "success"})
        actions.append({"target": Room.Status.VACANT_DIRTY, "label": "Mark Dirty", "btn_class": "danger"})
        actions.append({"target": Room.Status.UNDER_MAINTENANCE, "label": "Under Maintenance", "btn_class": "secondary"})

    elif s == Room.Status.VACANT_CLEAN:
        actions.append({"target": Room.Status.VACANT_DIRTY, "label": "Mark Dirty", "btn_class": "danger"})
        actions.append({"target": Room.Status.UNDER_MAINTENANCE, "label": "Under Maintenance", "btn_class": "secondary"})

    elif s == Room.Status.OCCUPIED:
        actions.append({"target": Room.Status.VACANT_DIRTY, "label": "Check Out / Dirty", "btn_class": "danger"})
        actions.append({"target": Room.Status.CLEANING_IN_PROGRESS, "label": "Start Cleaning", "btn_class": "warning"})
        actions.append({"target": Room.Status.UNDER_MAINTENANCE, "label": "Under Maintenance", "btn_class": "secondary"})

    elif s == Room.Status.UNDER_MAINTENANCE:
        actions.append({"target": Room.Status.VACANT_DIRTY, "label": "Clear Maintenance (Dirty)", "btn_class": "warning"})
        actions.append({"target": Room.Status.VACANT_CLEAN, "label": "Clear Maintenance (Clean)", "btn_class": "success"})

    elif s == Room.Status.BLOCKED:
        actions.append({"target": Room.Status.VACANT_CLEAN, "label": "Unblock (Clean)", "btn_class": "success"})
        actions.append({"target": Room.Status.VACANT_DIRTY, "label": "Unblock (Dirty)", "btn_class": "danger"})

    return actions
