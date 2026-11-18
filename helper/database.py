
import motor.motor_asyncio
from config import Config
from .utils import send_log


class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.jishubotz = self._client[database_name]
        self.col = self.jishubotz.user

    def new_user(self, id):
        return dict(
            _id=int(id),
            file_id=None,
            caption=None,
            prefix=None,
            suffix=None,
            metadata=False,
            metadata_code="By :- @MadflixBotz",
            metadata_mode=None,
            metadata_fields={}
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)
            await send_log(b, u)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)

    async def total_users_count(self):
        return await self.col.count_documents({})

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})

    # Thumbnail
    async def set_thumbnail(self, id, file_id):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'file_id': file_id}}
        )

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('file_id', None)

    # Caption
    async def set_caption(self, id, caption):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'caption': caption}}
        )

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('caption', None)

    # Prefix
    async def set_prefix(self, id, prefix):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'prefix': prefix}}
        )

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('prefix', None)

    # Suffix
    async def set_suffix(self, id, suffix):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'suffix': suffix}}
        )

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('suffix', None)

    # Metadata enabled/disabled
    async def set_metadata(self, id, bool_meta):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'metadata': bool_meta}},
            upsert=True
        )

    async def get_metadata(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('metadata', False)

    # Old metadata text methods
    async def set_metadata_code(self, id, metadata_code):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'metadata_code': metadata_code}},
            upsert=True
        )

    async def get_metadata_code(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('metadata_code', None)

    # Independent metadata settings
    async def set_metadata_mode(self, id, mode):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'metadata_mode': mode}},
            upsert=True
        )

    async def get_metadata_mode(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('metadata_mode')

    async def set_metadata_field(self, id, field, value):
        # Empty string explicitly clears a metadata field.
        # Missing key leaves the original value unchanged.
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {f'metadata_fields.{field}': value}},
            upsert=True
        )

    async def get_metadata_fields(self, id):
        user = await self.col.find_one({'_id': int(id)} ) or {}
        return user.get('metadata_fields', {}) or {}

    # Saved output mode
    async def set_output_mode(self, id, mode):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'output_mode': mode}},
            upsert=True
        )

    async def get_output_mode(self, id):
        user = await self.col.find_one({'_id': int(id)}) or {}
        return user.get('output_mode')

    async def clear_output_mode(self, id):
        await self.col.update_one(
            {'_id': int(id)},
            {'$unset': {'output_mode': ''}},
            upsert=True
        )


jishubotz = Database(Config.DATABASE_URL, Config.DATABASE_NAME)
